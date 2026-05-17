#!/usr/bin/env python3
"""
Chapter 5 — KV Cache Pressure demo client.

Ramps concurrency from 1 to max_concurrent over ~70 seconds,
using ~2000-token input prompts to push KV cache utilization.

Against chapter5_util_095 (port 8004): KV cache hits 90%+, preemptions occur.
Against chapter5_util_085 (port 8005): KV cache stays under 90%, no preemptions.

Usage:
    python chapters/chapter5_kv_pressure/client.py --port 8004
    python chapters/chapter5_kv_pressure/client.py --port 8005
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import aiohttp
import requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from client_benchmark import stream_chat_completion, discover_model, RequestSpec

# Base for building ~2000-token prompts
# ~150 words ≈ 200 tokens; repeat 10x ≈ 2000 tokens
_PARAGRAPH = (
    "In modern large language model serving infrastructure, memory management is a critical "
    "concern. The key-value (KV) cache stores attention keys and values for each token in "
    "the sequence, allowing the model to generate subsequent tokens without recomputing "
    "prior context. As sequence lengths grow, the KV cache consumes an increasingly large "
    "fraction of available GPU memory. PagedAttention, introduced in the vLLM paper, "
    "addresses this by organizing the KV cache into fixed-size pages analogous to virtual "
    "memory in operating systems. This allows non-contiguous memory allocation and efficient "
    "sharing of KV state across requests that share a common prefix, such as system prompts "
    "in multi-tenant deployments. When the KV cache fills, the scheduler must preempt "
    "in-flight requests, swapping their KV blocks to CPU memory and re-scheduling them "
    "later. Preemption adds latency and reduces throughput, so operators must tune "
    "gpu_memory_utilization to balance KV cache headroom against model weight memory. "
    "The tradeoff: higher utilization means more concurrent requests fit in memory, "
    "improving throughput, but leaves less headroom and triggers preemption sooner "
    "under bursty load. Monitoring vllm:num_preemptions_total in Prometheus reveals "
    "how often the scheduler is forced to preempt, which is a key signal for capacity planning."
)


def build_kv_pressure_prompt(i: int, prompt_tokens: int = 2000) -> list[dict]:
    repeats = max(1, prompt_tokens // 200)
    content = (_PARAGRAPH + " ") * repeats
    return [
        {"role": "system", "content": "You are a technical assistant."},
        {"role": "user", "content": (
            f"{content}\n\n"
            f"Based on the above passage, describe in 3 bullet points the key tradeoffs "
            f"when tuning gpu_memory_utilization in vLLM. Request {i}."
        )},
    ]


def scrape_kv_util(port: int) -> float | None:
    """Scrape vllm:gpu_cache_usage_perc from the server's /metrics endpoint."""
    try:
        resp = requests.get(f"http://localhost:{port}/metrics", timeout=2.0)
        for line in resp.text.splitlines():
            if line.startswith("vllm:gpu_cache_usage_perc"):
                parts = line.split()
                if len(parts) >= 2:
                    return float(parts[1]) * 100
    except Exception:
        pass
    return None


def scrape_preemptions(port: int) -> int | None:
    """Scrape vllm:num_preemptions_total from /metrics."""
    try:
        resp = requests.get(f"http://localhost:{port}/metrics", timeout=2.0)
        for line in resp.text.splitlines():
            if line.startswith("vllm:num_preemptions_total"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(float(parts[1]))
    except Exception:
        pass
    return None


async def run(args: argparse.Namespace) -> None:
    port = args.port
    base_url = f"http://localhost:{port}/v1"
    output_path = Path(args.output or f"/tmp/chapter5_port{port}.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    connector = aiohttp.TCPConnector(limit=args.max_concurrent + 5)
    t0 = time.time()
    in_flight: list[asyncio.Task] = []
    request_counter = 0
    lock = asyncio.Lock()

    with output_path.open("w") as out:
        async with aiohttp.ClientSession(connector=connector) as session:
            model = args.model or await discover_model(base_url, session)
            print(f"Model: {model}  Port: {port}")
            print(f"Ramping 1 → {args.max_concurrent} concurrent, +1 every {args.ramp_step_s}s")
            print(f"Prompt tokens: {args.prompt_tokens}  Output tokens: {args.output_tokens}")
            print(f"Output: {output_path}")
            print("")

            async def send_one(req_id: int) -> None:
                spec = RequestSpec(
                    request_id=f"kv_{req_id:04d}",
                    scenario="chapter5",
                    prompt_class="kv_pressure",
                    messages=build_kv_pressure_prompt(req_id, args.prompt_tokens),
                    max_tokens=args.output_tokens,
                    temperature=0.0,
                    arrival_offset_s=0.0,
                )
                result = await stream_chat_completion(session, base_url, model, spec, t0)
                kv_util = scrape_kv_util(port)
                preemptions = scrape_preemptions(port)
                record = {
                    "request_id": result.request_id,
                    "start_ts": result.start_ts,
                    "end_ts": result.end_ts,
                    "ttft_ms": result.ttft_ms,
                    "e2e_ms": result.e2e_ms,
                    "status": result.status,
                    "kv_util_pct": kv_util,
                    "preemptions_total": preemptions,
                }
                async with lock:
                    out.write(json.dumps(record) + "\n")
                    out.flush()
                    kv_str = f"{kv_util:.1f}%" if kv_util is not None else "?"
                    pr_str = str(preemptions) if preemptions is not None else "?"
                    ttft = f"{result.ttft_ms:.0f}ms" if result.ttft_ms else "ERR"
                    print(f"  {result.request_id}  TTFT={ttft}  KV={kv_str}  preemptions={pr_str}")

            target_concurrent = 0
            next_step = t0

            while True:
                now = time.time()

                # Ramp up target concurrency
                if now >= next_step and target_concurrent < args.max_concurrent:
                    target_concurrent += 1
                    next_step = now + args.ramp_step_s
                    print(f"\n[t={now-t0:.0f}s] Target concurrency: {target_concurrent}")

                # Remove completed tasks
                in_flight = [t for t in in_flight if not t.done()]

                # Launch new requests to fill concurrency target
                while len(in_flight) < target_concurrent:
                    request_counter += 1
                    task = asyncio.ensure_future(send_one(request_counter))
                    in_flight.append(task)

                # Stop when we've ramped up and waited for all to complete
                if target_concurrent >= args.max_concurrent and time.time() - next_step > 10:
                    break

                await asyncio.sleep(0.5)

            # Wait for remaining in-flight requests
            if in_flight:
                print(f"\nWaiting for {len(in_flight)} in-flight requests...")
                await asyncio.gather(*in_flight)

    print(f"\nKV pressure ramp complete. Results in {output_path}")

    # Print summary
    records = [json.loads(l) for l in output_path.read_text().splitlines() if l.strip()]
    kv_vals = [r["kv_util_pct"] for r in records if r.get("kv_util_pct") is not None]
    pr_vals = [r["preemptions_total"] for r in records if r.get("preemptions_total") is not None]
    if kv_vals:
        print(f"KV cache: max={max(kv_vals):.1f}%  final={kv_vals[-1]:.1f}%")
    if pr_vals:
        print(f"Preemptions: max={max(pr_vals)}  final={pr_vals[-1]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chapter 5 KV pressure ramp client")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--max-concurrent", type=int, default=20)
    parser.add_argument("--ramp-step-s", type=float, default=3.0)
    parser.add_argument("--prompt-tokens", type=int, default=2000,
                        help="Approximate prompt length in tokens. Increase to 3000-4000 if KV pressure insufficient.")
    parser.add_argument("--output-tokens", type=int, default=200)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
