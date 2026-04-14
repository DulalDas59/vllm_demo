from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


plt.rcParams["figure.figsize"] = (12, 6)


def find_run_dirs(results_root: Path) -> list[Path]:
    return sorted([p for p in results_root.iterdir() if p.is_dir() and (p / "summary.json").exists()])


def load_runs(results_root: Path) -> list[dict]:
    runs = []
    for run_dir in find_run_dirs(results_root):
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        csv_path = run_dir / "per_request.csv"
        df = pd.read_csv(csv_path) if csv_path.exists() else pd.DataFrame()
        runs.append({"dir": run_dir, "summary": summary, "df": df})
    # sweep directories are nested; load aggregate separately later.
    return runs


def plot_gantt_mixed_batching(runs: list[dict], output_dir: Path) -> None:
    candidates = [r for r in runs if r["summary"].get("scenario") == "mixed_batching"]
    if not candidates:
        return
    fig, ax = plt.subplots(figsize=(13, 6))
    y = 0
    labels = []
    for run in candidates[:2]:
        df = run["df"].copy().sort_values(["start_ts", "prompt_class"])
        label_prefix = run["summary"].get("label", "run")
        for _, row in df.iterrows():
            start = row["start_ts"]
            width = row["end_ts"] - row["start_ts"]
            color = "tab:blue" if row["prompt_class"] == "short" else "tab:orange"
            ax.barh(y, width, left=start, height=0.6, color=color, alpha=0.8)
            labels.append(f"{label_prefix}:{row['request_id']}")
            y += 1
        y += 1
    ax.set_title("Continuous batching demo: request execution timeline")
    ax.set_xlabel("Time since workload start (s)")
    ax.set_ylabel("Requests")
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_dir / "gantt_mixed_batching.png", dpi=150)
    plt.close(fig)


def plot_chunked_prefill_itl(runs: list[dict], output_dir: Path) -> None:
    candidates = [r for r in runs if r["summary"].get("scenario") == "chunked_prefill"]
    if not candidates:
        return
    fig, ax = plt.subplots(figsize=(13, 6))
    for run in candidates:
        df = run["df"].copy()
        if df.empty:
            continue
        shorts = df[df["prompt_class"] == "short"].sort_values("start_ts")
        if shorts.empty:
            continue
        ax.plot(
            shorts["start_ts"],
            shorts["ttft_ms"],
            marker="o",
            label=f"{run['summary'].get('label', 'run')} short TTFT",
        )
        longs = df[df["prompt_class"] == "long_prefill"]
        if not longs.empty:
            inject_t = float(longs.iloc[0]["start_ts"])
            ax.axvline(inject_t, linestyle="--", alpha=0.5)
    ax.set_title("Chunked prefill demo: short-request TTFT around long prompt injection")
    ax.set_xlabel("Request start time (s)")
    ax.set_ylabel("TTFT (ms)")
    ax.legend()
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_dir / "chunked_prefill_itl.png", dpi=150)
    plt.close(fig)


def plot_prefix_cache_ttft(runs: list[dict], output_dir: Path) -> None:
    candidates = [r for r in runs if r["summary"].get("scenario") == "prefix_cache"]
    if not candidates:
        return
    fig, ax = plt.subplots(figsize=(12, 6))
    for run in candidates:
        df = run["df"].copy().sort_values("start_ts")
        if df.empty:
            continue
        ax.plot(range(len(df)), df["ttft_ms"], marker="o", label=run["summary"].get("label", "run"))
    ax.set_title("Prefix caching demo: TTFT across repeated shared-prefix requests")
    ax.set_xlabel("Request index")
    ax.set_ylabel("TTFT (ms)")
    ax.legend()
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_dir / "prefix_cache_ttft.png", dpi=150)
    plt.close(fig)


def plot_concurrency_sweep(results_root: Path, output_dir: Path) -> None:
    sweep_dirs = sorted([p for p in results_root.iterdir() if p.is_dir() and "_sweep_" in p.name and (p / "aggregate_summary.json").exists()])
    if not sweep_dirs:
        return
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    for sweep_dir in sweep_dirs:
        agg = json.loads((sweep_dir / "aggregate_summary.json").read_text(encoding="utf-8"))
        df = pd.DataFrame(agg).sort_values("concurrency")
        label = sweep_dir.name.split("_sweep_", 1)[-1]
        ax1.plot(df["concurrency"], df["throughput_tokens_per_s"], marker="o", label=f"throughput:{label}")
        ax2.plot(df["concurrency"], df["e2e_p95_ms"], marker="s", linestyle="--", label=f"p95:{label}")
    ax1.set_title("Concurrency sweep: throughput vs tail latency")
    ax1.set_xlabel("Concurrency level")
    ax1.set_ylabel("Approx throughput (tokens/s)")
    ax2.set_ylabel("P95 end-to-end latency (ms)")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="best")
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_dir / "concurrency_sweep.png", dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate professor-friendly plots from vLLM demo result folders.")
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    results_root = Path(args.results_root)
    output_dir = Path(args.output_dir)
    runs = load_runs(results_root)

    plot_gantt_mixed_batching(runs, output_dir)
    plot_chunked_prefill_itl(runs, output_dir)
    plot_prefix_cache_ttft(runs, output_dir)
    plot_concurrency_sweep(results_root, output_dir)
    print(f"Saved plots to: {output_dir}")


if __name__ == "__main__":
    main()
