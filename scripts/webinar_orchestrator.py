#!/usr/bin/env python3
"""
Webinar orchestrator — start/stop vLLM servers per chapter.

Usage:
    python scripts/webinar_orchestrator.py start --chapter 1
    python scripts/webinar_orchestrator.py switch --chapter 2
    python scripts/webinar_orchestrator.py status
    python scripts/webinar_orchestrator.py stop
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import httpx
from rich.console import Console
from rich.table import Table

console = Console()

REPO_DIR = Path(__file__).parent.parent
SERVERS_DIR = REPO_DIR / "configs" / "vllm_servers"
STATE_FILE = Path("/tmp/nimbusai_orchestrator_state.json")
ACTIVE_PORT_FILE = Path("/tmp/nimbusai_active_port.txt")
HEALTH_TIMEOUT_S = 150

CHAPTER_CONFIGS: dict[int, list[dict]] = {
    1: [{"script": "chapter1_default.sh", "port": 8000}],
    2: [
        {"script": "chapter2_chunked_off.sh", "port": 8000},
        {"script": "chapter2_chunked_on.sh", "port": 8001},
    ],
    3: [
        {"script": "chapter3_prefix_off.sh", "port": 8002},
        {"script": "chapter3_prefix_on.sh", "port": 8003},
    ],
    4: [],  # No live servers for Chapter 4
    5: [
        {"script": "chapter5_util_095.sh", "port": 8004},
        {"script": "chapter5_util_085.sh", "port": 8005},
    ],
    6: [],  # No live servers for Chapter 6
}


@dataclass
class ProcessInfo:
    pid: int
    port: int
    config: str


@dataclass
class OrchestratorState:
    current_chapter: int
    running_processes: list[ProcessInfo]
    active_port: int | None


def _load_state() -> OrchestratorState | None:
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text())
        procs = [ProcessInfo(**p) for p in data.get("running_processes", [])]
        return OrchestratorState(
            current_chapter=data["current_chapter"],
            running_processes=procs,
            active_port=data.get("active_port"),
        )
    except Exception:
        return None


def _save_state(state: OrchestratorState) -> None:
    data = {
        "current_chapter": state.current_chapter,
        "running_processes": [asdict(p) for p in state.running_processes],
        "active_port": state.active_port,
    }
    STATE_FILE.write_text(json.dumps(data, indent=2))


def _write_active_port(port: int | None) -> None:
    if port is None:
        ACTIVE_PORT_FILE.write_text("")
    else:
        ACTIVE_PORT_FILE.write_text(str(port))


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _wait_for_health(port: int, timeout_s: int = HEALTH_TIMEOUT_S) -> bool:
    url = f"http://localhost:{port}/health"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=3.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def _kill_process(proc: ProcessInfo, graceful_timeout_s: int = 30) -> None:
    if not _is_alive(proc.pid):
        return
    os.kill(proc.pid, signal.SIGTERM)
    deadline = time.time() + graceful_timeout_s
    while time.time() < deadline:
        if not _is_alive(proc.pid):
            return
        time.sleep(1)
    if _is_alive(proc.pid):
        os.kill(proc.pid, signal.SIGKILL)


def _stop_all(state: OrchestratorState) -> None:
    if not state.running_processes:
        return
    console.print("[yellow]Stopping running servers...[/yellow]")
    for proc in state.running_processes:
        if _is_alive(proc.pid):
            console.print(f"  Stopping PID {proc.pid} (port {proc.port}, {proc.config})")
            _kill_process(proc)
        else:
            console.print(f"  PID {proc.pid} already dead (port {proc.port})")
    state.running_processes = []
    state.active_port = None
    _write_active_port(None)


def cmd_start(chapter: int) -> None:
    state = _load_state()
    if state and state.running_processes:
        still_alive = [p for p in state.running_processes if _is_alive(p.pid)]
        if still_alive:
            ports = [p.port for p in still_alive]
            console.print(f"[red]Servers already running on ports {ports}.[/red]")
            console.print("Run [bold]stop[/bold] first, or use [bold]switch --chapter N[/bold].")
            sys.exit(1)

    configs = CHAPTER_CONFIGS.get(chapter, [])
    if not configs:
        console.print(f"[yellow]Chapter {chapter} has no live servers (uses pre-computed data).[/yellow]")
        if state:
            state.current_chapter = chapter
            _save_state(state)
        return

    new_procs: list[ProcessInfo] = []
    for cfg in configs:
        script = SERVERS_DIR / cfg["script"]
        port = cfg["port"]
        if not script.exists():
            console.print(f"[red]Script not found: {script}[/red]")
            sys.exit(1)
        console.print(f"Starting [bold]{cfg['script']}[/bold] on port {port}...")
        log_file = open(f"/tmp/vllm_port{port}.log", "w")
        proc = subprocess.Popen(
            ["bash", str(script)],
            stdout=log_file,
            stderr=log_file,
            preexec_fn=os.setsid,
        )
        new_procs.append(ProcessInfo(pid=proc.pid, port=port, config=cfg["script"]))

    # Wait for all servers to be healthy
    all_ready = True
    for proc_info in new_procs:
        console.print(f"  Waiting for port {proc_info.port} (up to {HEALTH_TIMEOUT_S}s)...")
        if _wait_for_health(proc_info.port):
            console.print(f"  [green][ok] Port {proc_info.port} healthy[/green]")
        else:
            console.print(f"  [red][ERROR] Port {proc_info.port} did not come up in {HEALTH_TIMEOUT_S}s[/red]")
            console.print(f"         Check /tmp/vllm_port{proc_info.port}.log for details")
            all_ready = False

    active_port = new_procs[0].port if new_procs else None
    new_state = OrchestratorState(
        current_chapter=chapter,
        running_processes=new_procs,
        active_port=active_port,
    )
    _save_state(new_state)
    _write_active_port(active_port)

    if all_ready:
        ports = [p.port for p in new_procs]
        console.print(f"\n[bold green][ok] Chapter {chapter} ready.[/bold green]")
        console.print(f"  Active port: {active_port}   All ports: {ports}")
        console.print(f"  Background traffic targets: {active_port}")
    else:
        console.print(f"\n[red]Chapter {chapter} partially started — check logs above.[/red]")
        sys.exit(1)


def cmd_switch(chapter: int) -> None:
    state = _load_state()
    if state:
        _stop_all(state)
        _save_state(state)
    console.print("")
    cmd_start(chapter)


def cmd_stop() -> None:
    state = _load_state()
    if not state or not state.running_processes:
        console.print("[yellow]No servers tracked. Nothing to stop.[/yellow]")
        STATE_FILE.unlink(missing_ok=True)
        _write_active_port(None)
        return
    _stop_all(state)
    _save_state(state)
    STATE_FILE.unlink(missing_ok=True)
    ACTIVE_PORT_FILE.unlink(missing_ok=True)
    console.print("[green][ok] All servers stopped.[/green]")


def cmd_status() -> None:
    state = _load_state()
    if not state:
        console.print("[yellow]No orchestrator state found. No servers tracked.[/yellow]")
        return

    table = Table(title=f"Chapter {state.current_chapter} Server Status")
    table.add_column("PID", style="cyan")
    table.add_column("Port", style="cyan")
    table.add_column("Config")
    table.add_column("Health")
    table.add_column("Alive")

    for proc in state.running_processes:
        alive = "[green]yes[/green]" if _is_alive(proc.pid) else "[red]no[/red]"
        try:
            r = httpx.get(f"http://localhost:{proc.port}/health", timeout=2.0)
            health = "[green]ok[/green]" if r.status_code == 200 else f"[red]{r.status_code}[/red]"
        except Exception:
            health = "[red]unreachable[/red]"
        table.add_row(str(proc.pid), str(proc.port), proc.config, health, alive)

    console.print(table)
    console.print(f"Active port for background traffic: {state.active_port}")


def _handle_sigint(sig, frame):
    console.print("\n[yellow]Interrupted. Stopping all servers...[/yellow]")
    cmd_stop()
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="NimbusAI webinar orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Start servers for a chapter")
    p_start.add_argument("--chapter", type=int, required=True, choices=list(CHAPTER_CONFIGS))

    p_switch = sub.add_parser("switch", help="Stop current servers and start next chapter")
    p_switch.add_argument("--chapter", type=int, required=True, choices=list(CHAPTER_CONFIGS))

    sub.add_parser("stop", help="Stop all tracked servers")
    sub.add_parser("status", help="Show status of tracked servers")

    args = parser.parse_args()
    signal.signal(signal.SIGINT, _handle_sigint)

    if args.command == "start":
        cmd_start(args.chapter)
    elif args.command == "switch":
        cmd_switch(args.chapter)
    elif args.command == "stop":
        cmd_stop()
    elif args.command == "status":
        cmd_status()


if __name__ == "__main__":
    main()
