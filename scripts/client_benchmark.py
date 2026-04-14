from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import random
import statistics
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import aiohttp
import numpy as np


@dataclass
class RequestSpec:
    request_id: str
    scenario: str
    prompt_class: str
    messages: list[dict[str, str]]
    max_tokens: int
    temperature: float = 0.0
    arrival_offset_s: float = 0.0
    metadata: dict[str, Any] | None = None


@dataclass
class RequestResult:
    request_id: str
    scenario: str
    prompt_class: str
    arrival_offset_s: float
    start_ts: float
    first_token_ts: float | None
    end_ts: float
    ttft_ms: float | None
    e2e_ms: float
    itl_mean_ms: float | None
    itl_p95_ms: float | None
    output_chars: int
    approx_output_tokens: int
    prompt_chars: int
    status: str
    error: str | None
    metadata: dict[str, Any] | None = None


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def approx_tokens_from_text(text: str) -> int:
    # Very rough heuristic when tokenizer usage is unavailable from streaming response.
    return max(1, math.ceil(len(text) / 4)) if text else 0


async def discover_model(base_url: str, session: aiohttp.ClientSession) -> str:
    async with session.get(f"{base_url}/models", timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        payload = await resp.json()
    models = payload.get("data", [])
    if not models:
        raise RuntimeError("No models found at /v1/models")
    return models[0]["id"]


async def stream_chat_completion(
    session: aiohttp.ClientSession,
    base_url: str,
    model: str,
    spec: RequestSpec,
    global_t0: float,
) -> RequestResult:
    await asyncio.sleep(max(0.0, spec.arrival_offset_s))

    url = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": spec.messages,
        "temperature": spec.temperature,
        "max_tokens": spec.max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    prompt_text = "\n".join(m.get("content", "") for m in spec.messages)
    start_ts = time.time()
    first_token_ts: float | None = None
    token_event_times: list[float] = []
    final_text_parts: list[str] = []
    usage_completion_tokens: int | None = None

    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=None)) as resp:
            resp.raise_for_status()
            async for raw in resp.content:
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue

                if obj.get("usage") and obj["usage"].get("completion_tokens") is not None:
                    usage_completion_tokens = int(obj["usage"]["completion_tokens"])

                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    t = time.time()
                    if first_token_ts is None:
                        first_token_ts = t
                    token_event_times.append(t)
                    final_text_parts.append(content)

        end_ts = time.time()
        final_text = "".join(final_text_parts)
        approx_output_tokens = usage_completion_tokens or approx_tokens_from_text(final_text)

        if len(token_event_times) >= 2:
            itls = np.diff(token_event_times) * 1000.0
            itl_mean_ms = float(np.mean(itls))
            itl_p95_ms = float(np.percentile(itls, 95))
        else:
            itl_mean_ms = None
            itl_p95_ms = None

        ttft_ms = (first_token_ts - start_ts) * 1000.0 if first_token_ts else None
        return RequestResult(
            request_id=spec.request_id,
            scenario=spec.scenario,
            prompt_class=spec.prompt_class,
            arrival_offset_s=spec.arrival_offset_s,
            start_ts=start_ts - global_t0,
            first_token_ts=(first_token_ts - global_t0) if first_token_ts else None,
            end_ts=end_ts - global_t0,
            ttft_ms=ttft_ms,
            e2e_ms=(end_ts - start_ts) * 1000.0,
            itl_mean_ms=itl_mean_ms,
            itl_p95_ms=itl_p95_ms,
            output_chars=len(final_text),
            approx_output_tokens=approx_output_tokens,
            prompt_chars=len(prompt_text),
            status="ok",
            error=None,
            metadata=spec.metadata,
        )
    except Exception as exc:  # pylint: disable=broad-except
        end_ts = time.time()
        return RequestResult(
            request_id=spec.request_id,
            scenario=spec.scenario,
            prompt_class=spec.prompt_class,
            arrival_offset_s=spec.arrival_offset_s,
            start_ts=start_ts - global_t0,
            first_token_ts=None,
            end_ts=end_ts - global_t0,
            ttft_ms=None,
            e2e_ms=(end_ts - start_ts) * 1000.0,
            itl_mean_ms=None,
            itl_p95_ms=None,
            output_chars=0,
            approx_output_tokens=0,
            prompt_chars=len(prompt_text),
            status="error",
            error=str(exc),
            metadata=spec.metadata,
        )


LONG_PREFIX_BLOCK = (
    "You are a systems performance assistant. Carefully follow the operating policy, "
    "summarize technical evidence, keep outputs concise, and preserve experimental rigor. "
    "This instruction block is intentionally repeated to create a long shared prefix for prefix-caching tests. "
)

LONG_DOC_BLOCK = (
    "This is a synthetic long document used to create a heavy prefill workload. "
    "It contains repeated explanations about transformers, KV cache, scheduling, throughput, latency, fairness, and memory pressure. "
    "The purpose is to stress the prompt processing phase while keeping the final question simple. "
)


def build_short_prompt(i: int) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "You are a concise assistant."},
        {
            "role": "user",
            "content": f"Answer in one short sentence: what is the key difference between latency and throughput? Example id {i}.",
        },
    ]


def build_long_generation_prompt(i: int) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "You are a helpful technical writer."},
        {
            "role": "user",
            "content": (
                f"Write a detailed 400-word explanation of why batching matters in LLM serving. "
                f"Keep it structured and readable. Example id {i}."
            ),
        },
    ]


def build_shared_prefix_messages(i: int, prefix_repeat: int) -> list[dict[str, str]]:
    long_prefix = LONG_PREFIX_BLOCK * prefix_repeat
    return [
        {"role": "system", "content": long_prefix},
        {
            "role": "user",
            "content": f"Using the shared policy above, answer briefly: why does prefix caching reduce TTFT? Query {i}.",
        },
    ]


def build_long_doc_messages(repeat: int) -> list[dict[str, str]]:
    long_doc = LONG_DOC_BLOCK * repeat
    return [
        {"role": "system", "content": "You are a document analyst."},
        {
            "role": "user",
            "content": (
                f"Read the following synthetic report and answer in two bullet points.\n\n"
                f"{long_doc}\n\n"
                "Question: why can a long prefill hurt short interactive requests?"
            ),
        },
    ]


def poisson_offsets(rate: float, count: int) -> list[float]:
    if rate <= 0:
        return [0.0 for _ in range(count)]
    rng = random.Random(42)
    offsets = []
    t = 0.0
    for _ in range(count):
        t += rng.expovariate(rate)
        offsets.append(t)
    return offsets


def scenario_mixed_batching(args: argparse.Namespace) -> list[RequestSpec]:
    specs: list[RequestSpec] = []
    req_id = 0
    if args.serialized:
        offsets = [0.0 for _ in range(args.short_request_count + args.long_request_count)]
    else:
        offsets = poisson_offsets(args.request_rate, args.short_request_count + args.long_request_count)

    pairs: list[tuple[str, list[dict[str, str]], int]] = []
    for i in range(args.short_request_count):
        pairs.append(("short", build_short_prompt(i), args.short_max_tokens))
    for i in range(args.long_request_count):
        pairs.append(("long", build_long_generation_prompt(i), args.long_max_tokens))

    # Interleave short and long requests to make the scheduling effect visible.
    mixed_pairs = []
    shorts = [p for p in pairs if p[0] == "short"]
    longs = [p for p in pairs if p[0] == "long"]
    while shorts or longs:
        if shorts:
            mixed_pairs.append(shorts.pop(0))
        if longs:
            mixed_pairs.append(longs.pop(0))

    current_offset = 0.0
    for idx, (prompt_class, messages, max_tokens) in enumerate(mixed_pairs):
        if args.serialized:
            arrival = current_offset
            current_offset += args.serialized_gap_s
        else:
            arrival = offsets[idx]
        specs.append(
            RequestSpec(
                request_id=f"req_{req_id:03d}",
                scenario="mixed_batching",
                prompt_class=prompt_class,
                messages=messages,
                max_tokens=max_tokens,
                arrival_offset_s=arrival,
            )
        )
        req_id += 1
    return specs


def scenario_chunked_prefill(args: argparse.Namespace) -> list[RequestSpec]:
    specs: list[RequestSpec] = []
    offsets = poisson_offsets(args.request_rate, args.short_request_count)
    for i in range(args.short_request_count):
        specs.append(
            RequestSpec(
                request_id=f"short_{i:03d}",
                scenario="chunked_prefill",
                prompt_class="short",
                messages=build_short_prompt(i),
                max_tokens=args.short_max_tokens,
                arrival_offset_s=offsets[i],
            )
        )

    long_inject_at = offsets[min(len(offsets) - 1, max(1, len(offsets) // 3))] if offsets else 0.5
    specs.append(
        RequestSpec(
            request_id="long_prefill_000",
            scenario="chunked_prefill",
            prompt_class="long_prefill",
            messages=build_long_doc_messages(args.long_prompt_repeat),
            max_tokens=args.short_max_tokens,
            arrival_offset_s=long_inject_at,
            metadata={"is_long_injection": True},
        )
    )
    return specs


def scenario_prefix_cache(args: argparse.Namespace) -> list[RequestSpec]:
    specs: list[RequestSpec] = []
    for i in range(args.prefix_query_count):
        specs.append(
            RequestSpec(
                request_id=f"prefix_{i:03d}",
                scenario="prefix_cache",
                prompt_class="shared_prefix",
                messages=build_shared_prefix_messages(i, args.prefix_repeat),
                max_tokens=args.short_max_tokens,
                arrival_offset_s=i * args.prefix_gap_s,
                metadata={"request_index": i},
            )
        )
    return specs


def scenario_sweep(args: argparse.Namespace) -> list[RequestSpec]:
    # Placeholder. The sweep scenario is executed in stages in main().
    return []


def write_request_results_csv(results: list[RequestResult], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()) if results else [
            "request_id", "scenario", "prompt_class", "arrival_offset_s", "start_ts", "first_token_ts",
            "end_ts", "ttft_ms", "e2e_ms", "itl_mean_ms", "itl_p95_ms", "output_chars",
            "approx_output_tokens", "prompt_chars", "status", "error", "metadata"
        ])
        writer.writeheader()
        for row in results:
            d = asdict(row)
            d["metadata"] = json.dumps(d["metadata"]) if d.get("metadata") is not None else ""
            writer.writerow(d)


def summarize_results(results: list[RequestResult], scenario: str, label: str, extra: dict[str, Any]) -> dict[str, Any]:
    ok_results = [r for r in results if r.status == "ok"]
    summary: dict[str, Any] = {
        "scenario": scenario,
        "label": label,
        "request_count": len(results),
        "ok_count": len(ok_results),
        "error_count": len(results) - len(ok_results),
        "generated_at": datetime.now().isoformat(),
        **extra,
    }
    if ok_results:
        ttfts = [r.ttft_ms for r in ok_results if r.ttft_ms is not None]
        e2es = [r.e2e_ms for r in ok_results]
        itls = [r.itl_mean_ms for r in ok_results if r.itl_mean_ms is not None]
        tokens = sum(r.approx_output_tokens for r in ok_results)
        wall_s = max(r.end_ts for r in ok_results) - min(r.start_ts for r in ok_results)
        summary.update(
            {
                "ttft_mean_ms": statistics.mean(ttfts) if ttfts else None,
                "ttft_p95_ms": float(np.percentile(ttfts, 95)) if len(ttfts) >= 2 else (ttfts[0] if ttfts else None),
                "e2e_mean_ms": statistics.mean(e2es),
                "e2e_p95_ms": float(np.percentile(e2es, 95)) if len(e2es) >= 2 else e2es[0],
                "itl_mean_ms": statistics.mean(itls) if itls else None,
                "throughput_tokens_per_s": (tokens / wall_s) if wall_s > 0 else None,
                "wall_time_s": wall_s,
            }
        )
    return summary


async def run_specs(base_url: str, model: str, specs: list[RequestSpec], max_in_flight: int = 100) -> list[RequestResult]:
    connector = aiohttp.TCPConnector(limit=max_in_flight)
    async with aiohttp.ClientSession(connector=connector) as session:
        if not model:
            model = await discover_model(base_url, session)
        global_t0 = time.time()
        tasks = [stream_chat_completion(session, base_url, model, spec, global_t0) for spec in specs]
        results = await asyncio.gather(*tasks)
        return results


def ensure_run_dir(output_root: Path, scenario: str, label: str) -> Path:
    run_dir = output_root / f"{now_stamp()}_{scenario}_{label}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


async def execute_single_scenario(args: argparse.Namespace) -> Path:
    output_root = Path(args.output_root)
    run_dir = ensure_run_dir(output_root, args.scenario, args.label)

    if args.scenario == "mixed_batching":
        specs = scenario_mixed_batching(args)
    elif args.scenario == "chunked_prefill":
        specs = scenario_chunked_prefill(args)
    elif args.scenario == "prefix_cache":
        specs = scenario_prefix_cache(args)
    else:
        raise ValueError(f"Unsupported scenario for single execution: {args.scenario}")

    results = await run_specs(args.base_url, args.model, specs)
    write_request_results_csv(results, run_dir / "per_request.csv")
    summary = summarize_results(results, args.scenario, args.label, vars(args))
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "request_specs.json").write_text(json.dumps([asdict(s) for s in specs], indent=2), encoding="utf-8")
    return run_dir


async def execute_sweep(args: argparse.Namespace) -> Path:
    output_root = Path(args.output_root)
    run_dir = ensure_run_dir(output_root, args.scenario, args.label)
    sweep_values = [int(x.strip()) for x in args.sweep_values.split(",") if x.strip()]
    aggregate: list[dict[str, Any]] = []

    for concurrency in sweep_values:
        specs: list[RequestSpec] = []
        for i in range(args.requests_per_sweep):
            specs.append(
                RequestSpec(
                    request_id=f"c{concurrency:02d}_{i:03d}",
                    scenario="sweep",
                    prompt_class="sweep_short",
                    messages=build_short_prompt(i),
                    max_tokens=args.short_max_tokens,
                    arrival_offset_s=0.0 if i < concurrency else (i // max(1, concurrency)) * args.sweep_wave_gap_s,
                    metadata={"concurrency": concurrency},
                )
            )
        stage_dir = run_dir / f"concurrency_{concurrency:02d}"
        stage_dir.mkdir(parents=True, exist_ok=True)
        results = await run_specs(args.base_url, args.model, specs)
        write_request_results_csv(results, stage_dir / "per_request.csv")
        summary = summarize_results(results, "sweep", f"{args.label}_c{concurrency}", {**vars(args), "concurrency": concurrency})
        (stage_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        aggregate.append(summary)

    (run_dir / "aggregate_summary.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run vLLM demo workloads against the OpenAI-compatible server.")
    parser.add_argument("--base-url", default="http://localhost:8000/v1", help="vLLM OpenAI-compatible base URL")
    parser.add_argument("--model", default="", help="Model id. If omitted, the script queries /v1/models.")
    parser.add_argument("--scenario", choices=["mixed_batching", "chunked_prefill", "prefix_cache", "sweep"], required=True)
    parser.add_argument("--label", default="run", help="Label embedded into output directory names")
    parser.add_argument("--output-root", default="results", help="Directory where run artifacts will be stored")

    parser.add_argument("--short-request-count", type=int, default=12)
    parser.add_argument("--long-request-count", type=int, default=4)
    parser.add_argument("--requests-per-sweep", type=int, default=12)
    parser.add_argument("--serialized", action="store_true")
    parser.add_argument("--serialized-gap-s", type=float, default=0.2)
    parser.add_argument("--request-rate", type=float, default=2.0, help="Poisson arrival rate in requests/sec")
    parser.add_argument("--sweep-values", default="1,2,4,8,12")
    parser.add_argument("--sweep-wave-gap-s", type=float, default=0.2)

    parser.add_argument("--short-max-tokens", type=int, default=48)
    parser.add_argument("--long-max-tokens", type=int, default=300)
    parser.add_argument("--long-prompt-repeat", type=int, default=3500)
    parser.add_argument("--prefix-repeat", type=int, default=2000)
    parser.add_argument("--prefix-query-count", type=int, default=8)
    parser.add_argument("--prefix-gap-s", type=float, default=0.15)
    return parser.parse_args()


async def main_async() -> None:
    args = parse_args()
    if args.scenario == "sweep":
        run_dir = await execute_sweep(args)
    else:
        run_dir = await execute_single_scenario(args)
    print(f"Saved run artifacts to: {run_dir}")


if __name__ == "__main__":
    asyncio.run(main_async())
