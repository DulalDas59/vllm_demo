#!/usr/bin/env python3
"""
Chapter 4 — Capacity planning sweep.

Offline benchmarking script that generates the capacity table for Slide 19.

For each of four configurations, sweeps request rates and finds the saturation
point (highest rps where p95 TTFT < SLO threshold).

IMPORTANT: This script assumes vLLM servers are already running on the correct
ports. Start/stop the appropriate server before running each configuration.

Usage:
    python chapters/chapter4_capacity_planning/sweep.py \\
        --config baseline --port 8000 \\
        --hourly-rate 2.50 --slo-p95-ttft 500 \\
        --output precomputed/capacity_table.json

Full run (all four configs, requires manual server restart between each):
    python chapters/chapter4_capacity_planning/sweep.py --all-configs
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import aiohttp
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from client_benchmark import stream_chat_completion, discover_model, RequestSpec

REPO_DIR = Path(__file__).parent.parent.parent

# Per-config port assignments (server must be started manually before running)
CONFIG_PORTS = {
    "baseline": 8000,        # chapter2_chunked_off.sh with max-model-len 8192
    "chunked": 8001,         # chapter2_chunked_on.sh
    "prefix": 8003,          # chapter3_prefix_on.sh
    "both": 8003,            # chapter3_prefix_on.sh (chunked prefill is on by default in vLLM >=0.4)
}

CONFIG_DISPLAY = {
    "baseline": "Baseline",
    "chunked": "+ Chunked prefill",
    "prefix": "+ Prefix caching",
    "both": "+ Both",
}

RATES_RPS = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32]
SWEEP_DURATION_S = 90
SLO_P95_MS = 500.0
HOURLY_RATE_USD = 2.50
AVG_OUTPUT_TOKENS = 50


def build_helpdesk_prompt(i: int) -> list[dict]:
    questions = [
        "What is latency in distributed systems?",
        "Define throughput in one sentence.",
        "What is a GPU KV cache?",
        "Why does batching matter for LLMs?",
        "What is continuous batching?",
    ]
    return [
        {"role": "system", "content": "Answer in one sentence."},
        {"role": "user", "content": questions[i % len(questions)]},
    ]


def build_agent_prompt_simple(i: int) -> list[dict]:
    prefix = "You are an enterprise assistant.\n" * 300  # ~1200 tokens system
    return [
        {"role": "system", "content": prefix},
        {"role": "user", "content": f"Briefly summarize the three most important monitoring metrics for an LLM serving system. Query {i}."},
    ]


def cost_per_1m_tokens(saturation_rps: float, hourly_rate: float, avg_output_tokens: int) -> float:
    if saturation_rps <= 0:
        return 0.0
    tokens_per_hour = saturation_rps * avg_output_tokens * 3600
    return round((hourly_rate * 1_000_000) / tokens_per_hour, 2)


async def run_rate(
    base_url: str,
    model: str,
    rate_rps: float,
    duration_s: float,
    mix_agent_frac: float = 0.2,
) -> dict:
    """Run a mixed workload at rate_rps for duration_s seconds. Returns stats."""
    interval = 1.0 / rate_rps
    total_requests = int(rate_rps * duration_s)
    connector = aiohttp.TCPConnector(limit=total_requests + 10)
    results = []
    t0 = time.time()

    async with aiohttp.ClientSession(connector=connector) as session:
        async def fire_one(i: int, delay: float):
            await asyncio.sleep(delay)
            is_agent = (i % round(1 / mix_agent_frac) == 0) if mix_agent_frac > 0 else False
            messages = build_agent_prompt_simple(i) if is_agent else build_helpdesk_prompt(i)
            spec = RequestSpec(
                request_id=f"sweep_{i:04d}",
                scenario="sweep",
                prompt_class="agent" if is_agent else "helpdesk",
                messages=messages,
                max_tokens=200 if is_agent else 50,
                temperature=0.0,
                arrival_offset_s=0.0,
            )
            r = await stream_chat_completion(session, base_url, model, spec, t0)
            results.append(r)

        tasks = [fire_one(i, i * interval) for i in range(total_requests)]
        await asyncio.gather(*tasks)

    ok = [r for r in results if r.status == "ok" and r.ttft_ms is not None]
    if not ok:
        return {"rate_rps": rate_rps, "p95_ttft_ms": None, "throughput_tps": 0, "ok_count": 0}

    ttfts = [r.ttft_ms for r in ok]
    wall = max(r.end_ts for r in ok) - min(r.start_ts for r in ok)
    tokens = sum(r.approx_output_tokens for r in ok)
    return {
        "rate_rps": rate_rps,
        "p95_ttft_ms": float(np.percentile(ttfts, 95)),
        "p50_ttft_ms": float(np.percentile(ttfts, 50)),
        "throughput_tps": tokens / wall if wall > 0 else 0,
        "ok_count": len(ok),
        "error_count": len(results) - len(ok),
    }


async def sweep_config(
    base_url: str,
    config_name: str,
    slo_p95_ms: float,
    hourly_rate: float,
) -> dict:
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        model = await discover_model(base_url, session)

    print(f"\n{'='*60}")
    print(f"Config: {CONFIG_DISPLAY[config_name]}  ({base_url})")
    print(f"SLO: p95 TTFT < {slo_p95_ms}ms   Model: {model}")
    print(f"{'='*60}")

    rate_results = []
    last_passing_rps = 0.0
    last_passing_p95 = None

    for rate in RATES_RPS:
        print(f"  Rate {rate:2d} rps  ({SWEEP_DURATION_S}s) ...", end=" ", flush=True)
        stats = await run_rate(base_url, model, rate, SWEEP_DURATION_S)
        rate_results.append(stats)
        p95 = stats.get("p95_ttft_ms")
        if p95 is None:
            print(f"NO RESULTS (all errors)")
            break
        verdict = "PASS" if p95 < slo_p95_ms else "FAIL"
        print(f"p95={p95:.0f}ms  tps={stats['throughput_tps']:.1f}  {verdict}")
        if p95 < slo_p95_ms:
            last_passing_rps = rate
            last_passing_p95 = p95
        elif p95 > slo_p95_ms * 2:
            print(f"  Stopping sweep early (p95 > 2x SLO)")
            break

    saturation_rps = last_passing_rps
    sat_p95 = last_passing_p95 or (rate_results[-1]["p95_ttft_ms"] if rate_results else None)
    c_per_1m = cost_per_1m_tokens(saturation_rps, hourly_rate, AVG_OUTPUT_TOKENS)
    verdict = "Best" if config_name == "both" else ("Passes" if saturation_rps > 0 and sat_p95 and sat_p95 < slo_p95_ms else "Fails")

    return {
        "config": CONFIG_DISPLAY[config_name],
        "p95_ttft_ms": round(sat_p95) if sat_p95 else None,
        "saturation_rps": saturation_rps,
        "cost_per_1m_tokens": c_per_1m,
        "verdict": verdict,
        "rate_sweep": rate_results,
    }


async def run_all(args: argparse.Namespace) -> None:
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    configs = ["baseline", "chunked", "prefix", "both"]
    rows = []

    for config in configs:
        port = CONFIG_PORTS[config]
        base_url = f"http://localhost:{port}/v1"
        print(f"\n{'#'*60}")
        print(f"# Config: {config}  Port: {port}")
        print(f"# Make sure the right vLLM server is running on port {port}")
        input(f"# Press Enter when server is ready...")

        row = await sweep_config(base_url, config, args.slo_p95_ttft, args.hourly_rate)
        rows.append(row)
        print(f"\nResult: {json.dumps({k: v for k, v in row.items() if k != 'rate_sweep'}, indent=2)}")

    output_path.write_text(json.dumps(rows, indent=2))
    print(f"\n{'='*60}")
    print(f"Capacity table written to {output_path}")
    print(f"{'='*60}\n")
    for r in rows:
        print(f"  {r['config']:25s}  p95={r['p95_ttft_ms']}ms  sat={r['saturation_rps']}rps  "
              f"${r['cost_per_1m_tokens']}/1M  {r['verdict']}")


async def run_single(args: argparse.Namespace) -> None:
    base_url = f"http://localhost:{args.port}/v1"
    row = await sweep_config(base_url, args.config, args.slo_p95_ttft, args.hourly_rate)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing table if present, update or append
    existing = []
    if output_path.exists():
        existing = json.loads(output_path.read_text())
    existing = [r for r in existing if r.get("config") != row["config"]]
    existing.append(row)
    output_path.write_text(json.dumps(existing, indent=2))
    print(f"\nResult appended to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chapter 4 capacity planning sweep")
    parser.add_argument("--hourly-rate", type=float, default=HOURLY_RATE_USD)
    parser.add_argument("--slo-p95-ttft", type=float, default=SLO_P95_MS)
    parser.add_argument("--output", default="precomputed/capacity_table.json")
    parser.add_argument("--all-configs", action="store_true",
                        help="Run all four configs (requires manual server restart between each)")
    parser.add_argument("--config", choices=list(CONFIG_PORTS), help="Single config to run")
    parser.add_argument("--port", type=int, help="Port for single-config run")
    args = parser.parse_args()

    if args.all_configs:
        asyncio.run(run_all(args))
    elif args.config and args.port:
        asyncio.run(run_single(args))
    else:
        parser.error("Provide --all-configs, or --config + --port for a single run")


if __name__ == "__main__":
    main()
