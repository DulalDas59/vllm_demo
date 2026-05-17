#!/usr/bin/env python3
"""
Chapter 3 — Prefix Caching demo client.

Mode 'shared': 10 agent requests with identical 3600-token prefix, varying query.
  Against prefix_off (port 8002): every request pays ~800ms TTFT.
  Against prefix_on  (port 8003): req 1 = ~800ms, reqs 2-10 = ~140ms.

Mode 'thrash': 200 requests each with a UNIQUE 3600-token prefix.
  Used to pre-generate Slide 16's cache-thrashing chart.
  Against prefix_on (port 8003): hit rate spikes then collapses.

Usage:
    python chapters/chapter3_prefix_caching/client.py --port 8003 --mode shared
    python chapters/chapter3_prefix_caching/client.py --port 8003 --mode thrash --num-requests 200
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from client_benchmark import stream_chat_completion, discover_model, RequestSpec
from chapters.chapter3_prefix_caching.hierarchical_prompt import (
    build_agent_prompt, get_user_query
)

CHAPTER_DIR = Path(__file__).parent


def write_record(f, record: dict) -> None:
    f.write(json.dumps(record) + "\n")
    f.flush()


def _build_unique_prefix(length_chars: int, rng: random.Random) -> str:
    """Generate a unique ~3600-token prefix with no real shared structure."""
    words = [
        "quantum", "latency", "inference", "gradient", "optimizer", "kernel",
        "transform", "embedding", "attention", "softmax", "logit", "tensor",
        "batch", "sequence", "decoder", "encoder", "layer", "neuron", "weight",
        "activation", "dropout", "normalization", "residual", "pooling",
        "retrieval", "augmented", "generation", "pipeline", "orchestration",
    ]
    text = []
    while len(" ".join(text)) < length_chars:
        n = rng.randint(4, 12)
        sentence = " ".join(rng.choice(words) for _ in range(n))
        sentence = sentence.capitalize() + ". "
        text.append(sentence)
    return "".join(text)[:length_chars]


async def run_shared(
    base_url: str,
    model: str,
    num_requests: int,
    output_path: Path,
    gap_s: float,
) -> None:
    connector = aiohttp.TCPConnector(limit=5)
    t0 = time.time()

    with output_path.open("w") as out:
        async with aiohttp.ClientSession(connector=connector) as session:
            if not model:
                model = await discover_model(base_url, session)
            print(f"Model: {model}  Mode: shared  n={num_requests}")
            print(f"Output: {output_path}")
            print("")

            for i in range(num_requests):
                query = get_user_query(i)
                messages = build_agent_prompt(query)
                spec = RequestSpec(
                    request_id=f"agent_{i+1:03d}",
                    scenario="chapter3_shared",
                    prompt_class="agent",
                    messages=messages,
                    max_tokens=100,
                    temperature=0.0,
                    arrival_offset_s=0.0,
                    metadata={"request_index": i, "mode": "shared"},
                )
                result = await stream_chat_completion(session, base_url, model, spec, t0)
                record = {
                    "request_id": result.request_id,
                    "mode": "shared",
                    "request_index": i,
                    "start_ts": result.start_ts,
                    "end_ts": result.end_ts,
                    "ttft_ms": result.ttft_ms,
                    "status": result.status,
                }
                write_record(out, record)
                ttft = f"{result.ttft_ms:.0f}ms" if result.ttft_ms else "ERR"
                speedup = ""
                if i > 0 and result.ttft_ms:
                    first_ttft = None
                    lines = output_path.read_text().splitlines()
                    if lines:
                        first = json.loads(lines[0])
                        first_ttft = first.get("ttft_ms")
                    if first_ttft:
                        speedup = f"  ({first_ttft/result.ttft_ms:.1f}x vs req 1)"
                print(f"  req {i+1:02d}  TTFT={ttft}{speedup}")

                if i < num_requests - 1:
                    await asyncio.sleep(gap_s)

    print(f"\nShared prefix demo complete. Results in {output_path}")


async def run_thrash(
    base_url: str,
    model: str,
    num_requests: int,
    output_path: Path,
) -> None:
    connector = aiohttp.TCPConnector(limit=5)
    t0 = time.time()
    rng = random.Random(99)
    # ~3600 tokens × 4 chars/token ≈ 14400 chars for the prefix
    PREFIX_CHARS = 14_000

    with output_path.open("w") as out:
        async with aiohttp.ClientSession(connector=connector) as session:
            if not model:
                model = await discover_model(base_url, session)
            print(f"Model: {model}  Mode: thrash  n={num_requests}")
            print(f"Output: {output_path}")
            print("Sending requests with UNIQUE prefixes (cache thrash scenario)...")
            print("")

            for i in range(num_requests):
                unique_prefix = _build_unique_prefix(PREFIX_CHARS, rng)
                messages = [
                    {"role": "system", "content": unique_prefix},
                    {"role": "user", "content": f"Summarize the key points above. Request {i}."},
                ]
                spec = RequestSpec(
                    request_id=f"thrash_{i+1:03d}",
                    scenario="chapter3_thrash",
                    prompt_class="thrash",
                    messages=messages,
                    max_tokens=50,
                    temperature=0.0,
                    arrival_offset_s=0.0,
                    metadata={"request_index": i, "mode": "thrash"},
                )
                result = await stream_chat_completion(session, base_url, model, spec, t0)
                record = {
                    "request_id": result.request_id,
                    "mode": "thrash",
                    "request_index": i,
                    "start_ts": result.start_ts,
                    "end_ts": result.end_ts,
                    "ttft_ms": result.ttft_ms,
                    "status": result.status,
                }
                write_record(out, record)
                if i % 20 == 0:
                    print(f"  Progress: {i}/{num_requests}")

    print(f"\nThrash run complete. Results in {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chapter 3 prefix caching demo client")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--mode", choices=["shared", "thrash"], default="shared")
    parser.add_argument("--num-requests", type=int, default=10)
    parser.add_argument("--gap-s", type=float, default=1.0, help="Gap between requests (shared mode)")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    base_url = f"http://localhost:{args.port}/v1"
    if not args.output:
        args.output = f"/tmp/chapter3_{args.mode}_port{args.port}.jsonl"
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.mode == "shared":
        asyncio.run(run_shared(base_url, args.model, args.num_requests, output_path, args.gap_s))
    else:
        asyncio.run(run_thrash(base_url, args.model, args.num_requests, output_path))


if __name__ == "__main__":
    main()
