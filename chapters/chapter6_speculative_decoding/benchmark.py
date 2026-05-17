#!/usr/bin/env python3
"""
Chapter 6 — Speculative Decoding benchmark.

For each of three concurrency levels (c=1, c=4, c=16), measures throughput
with and without speculative decoding (ngram method).

Assumes two servers are running:
  - Port 8000: standard vLLM (no speculative decoding)
  - Port 8006: vLLM with --speculative-config ngram (see README)

Usage:
    python chapters/chapter6_speculative_decoding/benchmark.py
    python chapters/chapter6_speculative_decoding/benchmark.py \\
        --port-baseline 8000 --port-spec 8006 \\
        --output precomputed/speculative_results.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import aiohttp
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from client_benchmark import stream_chat_completion, discover_model, RequestSpec

BENCHMARK_DURATION_S = 60
CONCURRENCY_LEVELS = [1, 4, 16]

# ~200-500 token output prompts work best for speculative decoding (repetitive text)
GENERATION_PROMPTS = [
    "Write a detailed explanation of how transformers work, including self-attention, "
    "positional encoding, and the encoder-decoder architecture. Be thorough.",
    "Explain the history of deep learning from perceptrons to transformers, covering "
    "key milestones, architectures, and researchers. Write at least 400 words.",
    "Describe in detail how gradient descent and backpropagation work together to "
    "train a neural network. Include mathematical intuition.",
    "Write a comprehensive guide to hyperparameter tuning for large language models, "
    "covering learning rate scheduling, batch size, weight decay, and warmup steps.",
]


def build_generation_prompt(i: int) -> list[dict]:
    prompt = GENERATION_PROMPTS[i % len(GENERATION_PROMPTS)]
    return [
        {"role": "system", "content": "You are a detailed technical writer. Write comprehensive, structured explanations."},
        {"role": "user", "content": prompt},
    ]


async def benchmark_server(
    base_url: str,
    concurrency: int,
    duration_s: float,
) -> dict:
    connector = aiohttp.TCPConnector(limit=concurrency + 5)
    t0 = time.time()
    results = []
    req_counter = 0
    lock = asyncio.Lock()

    async with aiohttp.ClientSession(connector=connector) as session:
        model = await discover_model(base_url, session)
        in_flight: list[asyncio.Task] = []

        async def send_one(idx: int) -> None:
            spec = RequestSpec(
                request_id=f"spec_{idx:04d}",
                scenario="chapter6",
                prompt_class="generation",
                messages=build_generation_prompt(idx),
                max_tokens=300,
                temperature=0.0,
                arrival_offset_s=0.0,
            )
            r = await stream_chat_completion(session, base_url, model, spec, t0)
            async with lock:
                results.append(r)

        while time.time() - t0 < duration_s:
            in_flight = [t for t in in_flight if not t.done()]
            while len(in_flight) < concurrency:
                req_counter += 1
                task = asyncio.ensure_future(send_one(req_counter))
                in_flight.append(task)
            await asyncio.sleep(0.1)

        # Wait for remaining
        if in_flight:
            await asyncio.gather(*in_flight, return_exceptions=True)

    ok = [r for r in results if r.status == "ok"]
    if not ok:
        return {"tokens_per_sec": 0, "ok_count": 0, "model": model}

    wall = max(r.end_ts for r in ok) - min(r.start_ts for r in ok)
    total_tokens = sum(r.approx_output_tokens for r in ok)
    return {
        "tokens_per_sec": total_tokens / wall if wall > 0 else 0,
        "ok_count": len(ok),
        "error_count": len(results) - len(ok),
        "model": model,
    }


async def run_benchmark(args: argparse.Namespace) -> None:
    results = []

    for concurrency in CONCURRENCY_LEVELS:
        print(f"\n{'='*50}")
        print(f"Concurrency: {concurrency}  Duration: {BENCHMARK_DURATION_S}s each")
        print(f"{'='*50}")

        # Without speculative decoding
        print(f"  Running WITHOUT speculative decoding (port {args.port_baseline})...", flush=True)
        base_stats = await benchmark_server(
            f"http://localhost:{args.port_baseline}/v1",
            concurrency,
            BENCHMARK_DURATION_S,
        )
        print(f"  {base_stats['tokens_per_sec']:.1f} tokens/sec  ({base_stats['ok_count']} requests)")

        # With speculative decoding
        print(f"  Running WITH speculative decoding (port {args.port_spec})...", flush=True)
        spec_stats = await benchmark_server(
            f"http://localhost:{args.port_spec}/v1",
            concurrency,
            BENCHMARK_DURATION_S,
        )
        print(f"  {spec_stats['tokens_per_sec']:.1f} tokens/sec  ({spec_stats['ok_count']} requests)")

        ratio = (
            spec_stats["tokens_per_sec"] / base_stats["tokens_per_sec"]
            if base_stats["tokens_per_sec"] > 0
            else 0.0
        )
        print(f"  Ratio: {ratio:.2f}x")

        results.append({
            "concurrency": concurrency,
            "tokens_per_sec_without_spec": round(base_stats["tokens_per_sec"], 1),
            "tokens_per_sec_with_spec": round(spec_stats["tokens_per_sec"], 1),
            "ratio": round(ratio, 2),
        })

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))

    print(f"\n{'='*50}")
    print(f"Results written to {output_path}")
    print(f"{'='*50}")
    print(f"\n{'Concurrency':>12} {'Without spec':>14} {'With spec':>10} {'Ratio':>8}")
    print("-" * 50)
    for r in results:
        speedup = "FASTER" if r["ratio"] > 1.0 else "SLOWER"
        print(f"{r['concurrency']:>12}  {r['tokens_per_sec_without_spec']:>12.1f}  "
              f"{r['tokens_per_sec_with_spec']:>10.1f}  {r['ratio']:>7.2f}x  {speedup}")

    print(f"\nExpected: c=1 ~1.6x, c=4 ~1.05x, c=16 ~0.85x")
    print("If results differ significantly, update Slide 25 with actual numbers.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chapter 6 speculative decoding benchmark")
    parser.add_argument("--port-baseline", type=int, default=8000,
                        help="Port for standard vLLM server (no speculative decoding)")
    parser.add_argument("--port-spec", type=int, default=8006,
                        help="Port for speculative-decoding vLLM server")
    parser.add_argument("--output", default="precomputed/speculative_results.json")
    parser.add_argument("--duration", type=int, default=BENCHMARK_DURATION_S)
    args = parser.parse_args()
    asyncio.run(run_benchmark(args))


if __name__ == "__main__":
    main()
