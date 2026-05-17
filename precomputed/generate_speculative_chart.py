#!/usr/bin/env python3
"""
Generate the speculative decoding bar chart for Slide 25.

Reads from precomputed/speculative_results.json.
Falls back to demo data if the file doesn't exist yet.

Usage:
    python precomputed/generate_speculative_chart.py
    python precomputed/generate_speculative_chart.py \\
        --input precomputed/speculative_results.json \\
        --output precomputed/speculative_decoding_chart.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

DARK_BG = "#0D1117"
TEXT = "#E5E7EB"
GRID = "#374151"
GREEN = "#10B981"
GRAY = "#9CA3AF"
RED = "#EF4444"
AMBER = "#F59E0B"

plt.rcParams.update({
    "figure.facecolor": DARK_BG,
    "axes.facecolor": DARK_BG,
    "axes.edgecolor": GRID,
    "axes.labelcolor": TEXT,
    "xtick.color": TEXT,
    "ytick.color": TEXT,
    "text.color": TEXT,
    "grid.color": GRID,
    "font.family": "monospace",
    "font.size": 14,
    "axes.titlesize": 17,
    "axes.titleweight": "bold",
})

# Demo data (used if real benchmark hasn't been run yet)
DEMO_DATA = [
    {"concurrency": 1,  "ratio": 1.61},
    {"concurrency": 4,  "ratio": 1.05},
    {"concurrency": 16, "ratio": 0.85},
]


def load_data(path: Path) -> list[dict]:
    if path.exists():
        data = json.loads(path.read_text())
        return [{"concurrency": r["concurrency"], "ratio": r["ratio"]} for r in data]
    print(f"[warn] {path} not found — using demo data. Run benchmark.py first for real numbers.")
    return DEMO_DATA


def generate(input_path: str, output_path: str) -> None:
    data = load_data(Path(input_path))
    data.sort(key=lambda r: r["concurrency"])

    concurrencies = [str(r["concurrency"]) for r in data]
    ratios = [r["ratio"] for r in data]
    colors = []
    for ratio in ratios:
        if ratio > 1.15:
            colors.append(GREEN)
        elif ratio > 0.95:
            colors.append(GRAY)
        else:
            colors.append(RED)

    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)

    x = np.arange(len(concurrencies))
    bars = ax.bar(x, ratios, color=colors, width=0.5, edgecolor=DARK_BG, linewidth=2)

    # Baseline reference line
    ax.axhline(y=1.0, color=AMBER, linestyle="--", linewidth=2.0, alpha=0.8, label="baseline (no speculation)")

    # Value labels on bars
    for bar, ratio in zip(bars, ratios):
        height = bar.get_height()
        label_y = height + 0.02 if height >= 1.0 else height - 0.08
        va = "bottom" if height >= 1.0 else "top"
        ax.text(bar.get_x() + bar.get_width() / 2.0, label_y,
                f"{ratio:.2f}x", ha="center", va=va, fontsize=15, fontweight="bold",
                color=TEXT)

    ax.set_xticks(x)
    ax.set_xticklabels([f"c = {c}" for c in concurrencies], fontsize=14)
    ax.set_xlabel("Concurrency level", labelpad=10)
    ax.set_ylabel("Throughput ratio\n(with spec / without spec)", labelpad=10)
    ax.set_title("Speculative Decoding: Regime-Dependent Performance", pad=15)
    ax.set_ylim(0, max(ratios) * 1.25)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    legend_patches = [
        mpatches.Patch(color=GREEN, label="Speculation helps (>1.15x)"),
        mpatches.Patch(color=GRAY, label="Roughly neutral (0.95-1.15x)"),
        mpatches.Patch(color=RED, label="Speculation hurts (<0.95x)"),
        plt.Line2D([0], [0], color=AMBER, linestyle="--", linewidth=2, label="baseline (no speculation)"),
    ]
    ax.legend(handles=legend_patches, loc="upper right", framealpha=0.15,
              facecolor=DARK_BG, fontsize=12)

    # Annotation explaining the tradeoff
    ax.text(0.5, 0.08,
            "Low concurrency: speculation amortizes well.\n"
            "High concurrency: verification overhead dominates.",
            transform=ax.transAxes, ha="center", fontsize=12, color=TEXT,
            alpha=0.7, style="italic")

    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    print(f"Saved: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="precomputed/speculative_results.json")
    parser.add_argument("--output", default="precomputed/speculative_decoding_chart.png")
    args = parser.parse_args()
    generate(args.input, args.output)


if __name__ == "__main__":
    main()
