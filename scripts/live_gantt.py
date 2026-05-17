#!/usr/bin/env python3
"""
Live-updating Gantt chart for the Chapter 1 continuous batching demo.

Reads per-request records from a JSONL file written by the Chapter 1 client
and renders a horizontal bar chart that updates as new requests complete.

Usage:
    # Single file
    python scripts/live_gantt.py --watch-file /tmp/chapter1_concurrent.jsonl

    # Split mode (serial vs concurrent side-by-side)
    python scripts/live_gantt.py --split \\
        --left /tmp/chapter1_serial.jsonl --left-title "Serial Dispatch" \\
        --right /tmp/chapter1_concurrent.jsonl --right-title "Concurrent Dispatch"
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import matplotlib
matplotlib.use("TkAgg")  # Works over SSH with X forwarding; fall back to Qt if needed
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation


DARK_BG = "#0D1117"
GREEN_OK = "#10B981"
RED_ERR = "#EF4444"
TEXT_COLOR = "#E5E7EB"
GRID_COLOR = "#374151"

plt.rcParams.update({
    "figure.facecolor": DARK_BG,
    "axes.facecolor": DARK_BG,
    "axes.edgecolor": GRID_COLOR,
    "axes.labelcolor": TEXT_COLOR,
    "xtick.color": TEXT_COLOR,
    "ytick.color": TEXT_COLOR,
    "text.color": TEXT_COLOR,
    "grid.color": GRID_COLOR,
    "grid.linestyle": "--",
    "grid.alpha": 0.5,
    "font.size": 13,
    "axes.titlesize": 16,
    "axes.titleweight": "bold",
    "font.family": "monospace",
})


def read_jsonl(path: Path, state: dict) -> list[dict]:
    """Read new lines from a JSONL file since the last read position."""
    records = state.setdefault("records", [])
    pos = state.setdefault("pos", 0)

    try:
        with path.open("r") as f:
            f.seek(pos)
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            state["pos"] = f.tell()
    except FileNotFoundError:
        pass

    return records


def draw_gantt(ax: plt.Axes, records: list[dict], title: str) -> None:
    ax.clear()
    ax.set_facecolor(DARK_BG)
    ax.set_title(title, pad=12)
    ax.set_xlabel("Wall time (seconds)")
    ax.set_ylabel("Request #")
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    if not records:
        ax.text(0.5, 0.5, "Waiting for requests...", transform=ax.transAxes,
                ha="center", va="center", fontsize=15, color=TEXT_COLOR, alpha=0.6)
        return

    max_end = max(r.get("end_ts", 0) for r in records) or 1.0
    ax.set_xlim(0, max_end * 1.05)
    ax.set_ylim(0, len(records) + 1)
    ax.set_yticks(range(1, len(records) + 1))
    ax.set_yticklabels([f"req {i+1:02d}" for i in range(len(records))])

    for i, rec in enumerate(records):
        y = i + 1
        start = rec.get("start_ts", 0.0)
        end = rec.get("end_ts", start + 0.1)
        color = GREEN_OK if rec.get("status") == "ok" else RED_ERR
        ax.barh(y, end - start, left=start, color=color, height=0.6, alpha=0.85)

        # Mark TTFT with a thin vertical line inside the bar
        ttft_ms = rec.get("ttft_ms")
        if ttft_ms is not None:
            ttft_s = ttft_ms / 1000.0
            ax.axvline(x=start + ttft_s, ymin=(y - 0.3) / (len(records) + 1),
                       ymax=(y + 0.3) / (len(records) + 1),
                       color="white", linewidth=1.5, alpha=0.6)

    legend_patches = [
        mpatches.Patch(color=GREEN_OK, label="ok"),
        mpatches.Patch(color=RED_ERR, label="error"),
        mpatches.Patch(color="white", label="TTFT mark"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", framealpha=0.2,
              fontsize=11, facecolor=DARK_BG)

    # Summary stats
    ok = [r for r in records if r.get("status") == "ok"]
    if ok:
        wall = max_end - min(r.get("start_ts", 0) for r in ok)
        ttfts = [r["ttft_ms"] for r in ok if r.get("ttft_ms") is not None]
        stats = f"n={len(ok)}  wall={wall:.1f}s"
        if ttfts:
            stats += f"  TTFT p50={sorted(ttfts)[len(ttfts)//2]:.0f}ms"
        ax.text(0.02, 0.02, stats, transform=ax.transAxes, fontsize=11,
                color=TEXT_COLOR, alpha=0.8, va="bottom")


def main() -> None:
    parser = argparse.ArgumentParser(description="Live Gantt chart for Chapter 1 demo")
    parser.add_argument("--watch-file", help="JSONL file to watch (single mode)")
    parser.add_argument("--title", default="vLLM Request Dispatch", help="Chart title")
    parser.add_argument("--split", action="store_true", help="Side-by-side split mode")
    parser.add_argument("--left", help="Left panel JSONL file (split mode)")
    parser.add_argument("--left-title", default="Serial Dispatch")
    parser.add_argument("--right", help="Right panel JSONL file (split mode)")
    parser.add_argument("--right-title", default="Concurrent Dispatch")
    parser.add_argument("--poll-ms", type=int, default=200, help="Poll interval in ms")
    args = parser.parse_args()

    if args.split:
        if not args.left or not args.right:
            parser.error("--split requires --left and --right")
        fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(20, 10))
        fig.patch.set_facecolor(DARK_BG)
        fig.suptitle("NimbusAI · Continuous Batching Demo", fontsize=20,
                     color=TEXT_COLOR, fontweight="bold")

        left_state: dict = {}
        right_state: dict = {}

        def update_split(frame):
            left_records = read_jsonl(Path(args.left), left_state)
            right_records = read_jsonl(Path(args.right), right_state)
            draw_gantt(ax_left, left_records, args.left_title)
            draw_gantt(ax_right, right_records, args.right_title)
            fig.tight_layout(rect=[0, 0, 1, 0.95])

        ani = FuncAnimation(fig, update_split, interval=args.poll_ms, cache_frame_data=False)

    else:
        if not args.watch_file:
            parser.error("Provide --watch-file or use --split mode")
        fig, ax = plt.subplots(1, 1, figsize=(14, 10))
        fig.patch.set_facecolor(DARK_BG)

        file_state: dict = {}

        def update_single(frame):
            records = read_jsonl(Path(args.watch_file), file_state)
            draw_gantt(ax, records, args.title)
            fig.tight_layout()

        ani = FuncAnimation(fig, update_single, interval=args.poll_ms, cache_frame_data=False)

    plt.show()


if __name__ == "__main__":
    main()
