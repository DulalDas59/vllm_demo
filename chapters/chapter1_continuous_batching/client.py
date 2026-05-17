#!/usr/bin/env python3
"""
Chapter 1 — Continuous Batching demo client.

Serial mode:   20 requests, one at a time. Target ~22s wall time.
Concurrent mode: 20 requests, all at once. Target ~3s wall time.

Writes per-request JSONL records live so live_gantt.py can tail them.

Usage:
    python chapters/chapter1_continuous_batching/client.py --mode serial
    python chapters/chapter1_continuous_batching/client.py --mode concurrent
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from client_benchmark import stream_chat_completion, discover_model, RequestSpec

SHORT_QUESTIONS = [
    "What is the key difference between latency and throughput?",
    "Why does batching improve GPU efficiency in LLM serving?",
    "What does TTFT stand for in LLM serving?",
    "Why is memory bandwidth a bottleneck for autoregressive decoding?",
    "What is PagedAttention and why was it invented?",
    "How does continuous batching differ from static batching?",
    "What is the KV cache and what does it store?",
    "Why does a long prompt slow down short requests without chunked prefill?",
    "What is prefix caching and when does it help?",
    "How does speculative decoding speed up generation?",
    "What metric do SLOs for chatbots most commonly target?",
    "What is GPU memory utilization in vLLM?",
    "Why is inter-token latency different from TTFT?",
    "What is a decode step in an autoregressive LLM?",
    "What causes request queuing in a vLLM server?",
    "What is a preemption in vLLM's scheduler?",
    "Why does high concurrency help throughput but hurt latency?",
    "What is the difference between prefill and decode phases?",
    "Why do attention computations scale quadratically with sequence length?",
    "What is a flash attention kernel and why does it matter?",
]


def build_prompt(i: int) -> list[dict]:
    return [
        {"role": "system", "content": "You are a concise assistant. Answer in exactly one sentence."},
        {"role": "user", "content": SHORT_QUESTIONS[i % len(SHORT_QUESTIONS)]},
    ]


def write_record(f, record: dict) -> None:
    f.write(json.dumps(record) + "\n")
    f.flush()


async def run_serial(
    base_url: str,
    model: str,
    num_requests: int,
    output_path: Path,
) -> None:
    connector = aiohttp.TCPConnector(limit=5)
    t0 = time.time()
    with output_path.open("w") as out:
        async with aiohttp.ClientSession(connector=connector) as session:
            if not model:
                model = await discover_model(base_url, session)
            print(f"Model: {model}")
            print(f"Mode: serial  n={num_requests}")
            print(f"Output: {output_path}")
            print("")

            for i in range(num_requests):
                spec = RequestSpec(
                    request_id=f"req_{i+1:03d}",
                    scenario="chapter1",
                    prompt_class="short",
                    messages=build_prompt(i),
                    max_tokens=50,
                    temperature=0.0,
                    arrival_offset_s=0.0,
                )
                result = await stream_chat_completion(session, base_url, model, spec, t0)
                record = {
                    "request_id": result.request_id,
                    "mode": "serial",
                    "start_ts": result.start_ts,
                    "first_token_ts": result.first_token_ts,
                    "end_ts": result.end_ts,
                    "ttft_ms": result.ttft_ms,
                    "e2e_ms": result.e2e_ms,
                    "output_tokens": result.approx_output_tokens,
                    "status": result.status,
                    "error": result.error,
                }
                write_record(out, record)
                status_icon = "✓" if result.status == "ok" else "✗"
                ttft = f"{result.ttft_ms:.0f}ms" if result.ttft_ms else "N/A"
                e2e = f"{result.e2e_ms:.0f}ms"
                print(f"  {status_icon} req {i+1:02d}  TTFT={ttft}  e2e={e2e}")

    wall = time.time() - t0
    print(f"\nSerial total wall time: {wall:.1f}s")


async def run_concurrent(
    base_url: str,
    model: str,
    num_requests: int,
    output_path: Path,
) -> None:
    connector = aiohttp.TCPConnector(limit=num_requests + 5)
    t0 = time.time()
    lock = asyncio.Lock()

    with output_path.open("w") as out:
        async with aiohttp.ClientSession(connector=connector) as session:
            if not model:
                model = await discover_model(base_url, session)
            print(f"Model: {model}")
            print(f"Mode: concurrent  n={num_requests}")
            print(f"Output: {output_path}")
            print("")

            async def run_one(i: int):
                spec = RequestSpec(
                    request_id=f"req_{i+1:03d}",
                    scenario="chapter1",
                    prompt_class="short",
                    messages=build_prompt(i),
                    max_tokens=50,
                    temperature=0.0,
                    arrival_offset_s=0.0,
                )
                result = await stream_chat_completion(session, base_url, model, spec, t0)
                record = {
                    "request_id": result.request_id,
                    "mode": "concurrent",
                    "start_ts": result.start_ts,
                    "first_token_ts": result.first_token_ts,
                    "end_ts": result.end_ts,
                    "ttft_ms": result.ttft_ms,
                    "e2e_ms": result.e2e_ms,
                    "output_tokens": result.approx_output_tokens,
                    "status": result.status,
                    "error": result.error,
                }
                async with lock:
                    write_record(out, record)
                    status_icon = "✓" if result.status == "ok" else "✗"
                    ttft = f"{result.ttft_ms:.0f}ms" if result.ttft_ms else "N/A"
                    print(f"  {status_icon} {result.request_id}  TTFT={ttft}  e2e={result.e2e_ms:.0f}ms")

            await asyncio.gather(*[run_one(i) for i in range(num_requests)])

    wall = time.time() - t0
    print(f"\nConcurrent total wall time: {wall:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chapter 1 continuous batching demo client")
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--model", default="")
    parser.add_argument("--mode", choices=["serial", "concurrent"], required=True)
    parser.add_argument("--num-requests", type=int, default=20)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    if not args.output:
        args.output = f"/tmp/chapter1_{args.mode}.jsonl"

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.mode == "serial":
        asyncio.run(run_serial(args.base_url, args.model, args.num_requests, output_path))
    else:
        asyncio.run(run_concurrent(args.base_url, args.model, args.num_requests, output_path))


if __name__ == "__main__":
    main()
