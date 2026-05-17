#!/usr/bin/env python3
"""
Always-on background traffic generator.

Sends ~2 HelpDesk-style short requests/sec to the currently-active vLLM server
so the Grafana dashboard panels show recent activity during slides.

The active port is read from /tmp/nimbusai_active_port.txt (single integer).
The orchestrator updates this file when switching chapters.

Usage:
    python scripts/background_traffic.py
    python scripts/background_traffic.py --port-file /tmp/nimbusai_active_port.txt --rps 2
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import logging.handlers
import time
from pathlib import Path

import aiohttp

SHORT_PROMPTS = [
    "In one sentence, what is latency?",
    "In one sentence, what is throughput?",
    "In one sentence, why does batching matter for LLMs?",
    "In one sentence, what is a GPU KV cache?",
    "In one sentence, what is continuous batching?",
    "In one sentence, what is prefix caching?",
    "In one sentence, what is TTFT?",
    "In one sentence, what is inter-token latency?",
    "In one sentence, why do transformers use attention?",
    "In one sentence, what is speculative decoding?",
    "In one sentence, what is PagedAttention?",
    "In one sentence, what is chunked prefill?",
]


def setup_logger(log_file: str) -> logging.Logger:
    logger = logging.getLogger("background_traffic")
    logger.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=2
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def read_active_port(port_file: Path) -> int | None:
    try:
        text = port_file.read_text().strip()
        if text:
            return int(text)
    except Exception:
        pass
    return None


async def send_one_request(
    session: aiohttp.ClientSession,
    port: int,
    prompt_idx: int,
    logger: logging.Logger,
) -> None:
    prompt = SHORT_PROMPTS[prompt_idx % len(SHORT_PROMPTS)]
    url = f"http://localhost:{port}/v1/chat/completions"
    payload = {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "messages": [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 30,
        "temperature": 0.0,
        "stream": False,
    }
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                logger.debug(f"port={port} ok")
            else:
                logger.warning(f"port={port} status={resp.status}")
    except Exception as exc:
        logger.debug(f"port={port} error: {exc}")


async def run(port_file: Path, rps: float, log_file: str) -> None:
    logger = setup_logger(log_file)
    logger.info(f"Background traffic started. port_file={port_file} rps={rps}")

    interval = 1.0 / rps
    prompt_idx = 0
    last_port_check = 0.0
    current_port: int | None = None

    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            now = time.time()

            # Re-read port file every 10 seconds
            if now - last_port_check >= 10.0:
                new_port = read_active_port(port_file)
                if new_port != current_port:
                    logger.info(f"Active port changed: {current_port} → {new_port}")
                    current_port = new_port
                last_port_check = now

            if current_port is not None:
                asyncio.ensure_future(
                    send_one_request(session, current_port, prompt_idx, logger)
                )
                prompt_idx += 1

            await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="NimbusAI background traffic generator")
    parser.add_argument(
        "--port-file",
        default="/tmp/nimbusai_active_port.txt",
        help="File containing the active server port (single integer)",
    )
    parser.add_argument("--rps", type=float, default=2.0, help="Requests per second")
    parser.add_argument("--log-file", default="/tmp/background_traffic.log")
    args = parser.parse_args()

    asyncio.run(run(Path(args.port_file), args.rps, args.log_file))


if __name__ == "__main__":
    main()
