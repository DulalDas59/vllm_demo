#!/usr/bin/env python3
"""
Chapter 2 — Noisy Neighbor (Chunked Prefill) demo client.

Two-tenant simulation:
  - HelpDesk Hero: 1 short request/sec for 60 seconds
  - Legal Titan: one 30K-token request injected at T=10s

Run against chapter2_chunked_off (port 8000) to see TTFT spike.
Run against chapter2_chunked_on  (port 8001) to see TTFT stay flat.

Usage:
    python chapters/chapter2_noisy_neighbor/client.py --port 8000
    python chapters/chapter2_noisy_neighbor/client.py --port 8001
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

CHAPTER_DIR = Path(__file__).parent
CONTRACT_FILE = CHAPTER_DIR / "legal_contract_30k.txt"

HELPDESK_PROMPTS = [
    "I can't log into the HR portal. What should I do?",
    "How do I submit a reimbursement request?",
    "What are the office hours for IT support?",
    "How do I access the VPN from home?",
    "My laptop is running slow. Who do I contact?",
    "Where do I find the company holiday schedule?",
    "How do I request a new software license?",
    "What is the process for booking a meeting room?",
    "I forgot my email password. How do I reset it?",
    "How do I enroll in the health insurance plan?",
    "Where is the company handbook stored?",
    "How do I request work-from-home approval?",
]


def write_record(f, record: dict) -> None:
    f.write(json.dumps(record) + "\n")
    f.flush()


async def helpdesk_stream(
    session: aiohttp.ClientSession,
    base_url: str,
    model: str,
    duration_s: float,
    output_file,
    lock: asyncio.Lock,
    t0: float,
) -> None:
    """Send 1 short HelpDesk request/sec for duration_s seconds."""
    i = 0
    while time.time() - t0 < duration_s:
        prompt = HELPDESK_PROMPTS[i % len(HELPDESK_PROMPTS)]
        spec = RequestSpec(
            request_id=f"helpdesk_{i:03d}",
            scenario="chapter2",
            prompt_class="helpdesk",
            messages=[
                {"role": "system", "content": "You are a helpful IT assistant. Answer briefly."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=50,
            temperature=0.0,
            arrival_offset_s=0.0,
        )
        result = await stream_chat_completion(session, base_url, model, spec, t0)
        record = {
            "request_id": result.request_id,
            "tenant": "helpdesk",
            "start_ts": result.start_ts,
            "end_ts": result.end_ts,
            "ttft_ms": result.ttft_ms,
            "status": result.status,
        }
        async with lock:
            write_record(output_file, record)
            ttft = f"{result.ttft_ms:.0f}ms" if result.ttft_ms else "ERR"
            print(f"  HelpDesk {result.request_id}  TTFT={ttft}  t={result.start_ts:.1f}s")
        i += 1
        await asyncio.sleep(max(0, 1.0 - result.e2e_ms / 1000.0))


async def legal_inject(
    session: aiohttp.ClientSession,
    base_url: str,
    model: str,
    inject_at_s: float,
    output_file,
    lock: asyncio.Lock,
    t0: float,
) -> None:
    """Wait until inject_at_s, then send one 30K-token Legal Titan request."""
    wait = inject_at_s - (time.time() - t0)
    if wait > 0:
        await asyncio.sleep(wait)

    contract_text = CONTRACT_FILE.read_text(encoding="utf-8")
    prompt = f"Please summarize the key clauses in this contract:\n\n{contract_text}"
    print(f"\n  >>> Legal Titan injection at T={time.time()-t0:.1f}s <<<\n")

    spec = RequestSpec(
        request_id="legal_titan_000",
        scenario="chapter2",
        prompt_class="legal",
        messages=[
            {"role": "system", "content": "You are a legal document analyst. Be concise."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=200,
        temperature=0.0,
        arrival_offset_s=0.0,
    )
    result = await stream_chat_completion(session, base_url, model, spec, t0)
    record = {
        "request_id": result.request_id,
        "tenant": "legal",
        "start_ts": result.start_ts,
        "end_ts": result.end_ts,
        "ttft_ms": result.ttft_ms,
        "e2e_ms": result.e2e_ms,
        "status": result.status,
    }
    async with lock:
        write_record(output_file, record)
        ttft = f"{result.ttft_ms:.0f}ms" if result.ttft_ms else "ERR"
        print(f"  Legal Titan done: TTFT={ttft}  e2e={result.e2e_ms:.0f}ms")


async def run(args: argparse.Namespace) -> None:
    port = args.port
    base_url = f"http://localhost:{port}/v1"
    output_path = Path(args.output or f"/tmp/chapter2_port{port}.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not CONTRACT_FILE.exists():
        print(f"[ERROR] Legal contract file not found: {CONTRACT_FILE}")
        print("Run: python chapters/chapter2_noisy_neighbor/generate_contract.py")
        sys.exit(1)

    connector = aiohttp.TCPConnector(limit=20)
    t0 = time.time()
    lock = asyncio.Lock()

    with output_path.open("w") as out:
        async with aiohttp.ClientSession(connector=connector) as session:
            model = args.model or await discover_model(base_url, session)
            print(f"Model: {model}  Port: {port}")
            print(f"HelpDesk: 1 req/sec for {args.duration}s")
            print(f"Legal injection: at T={args.inject_at}s")
            print(f"Output: {output_path}")
            print("")

            await asyncio.gather(
                helpdesk_stream(session, base_url, model, args.duration, out, lock, t0),
                legal_inject(session, base_url, model, args.inject_at, out, lock, t0),
            )

    print(f"\nDone. Results written to {output_path}")
    # Quick summary
    records = [json.loads(l) for l in output_path.read_text().splitlines() if l.strip()]
    helpdesk = [r for r in records if r.get("tenant") == "helpdesk" and r.get("ttft_ms")]
    if helpdesk:
        ttfts = sorted(r["ttft_ms"] for r in helpdesk)
        n = len(ttfts)
        print(f"HelpDesk TTFT: n={n}  p50={ttfts[n//2]:.0f}ms  p95={ttfts[int(n*0.95)]:.0f}ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chapter 2 noisy-neighbor demo client")
    parser.add_argument("--port", type=int, required=True, help="vLLM server port")
    parser.add_argument("--model", default="")
    parser.add_argument("--duration", type=float, default=60.0, help="HelpDesk stream duration (s)")
    parser.add_argument("--inject-at", type=float, default=10.0, help="Legal injection time (s)")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
