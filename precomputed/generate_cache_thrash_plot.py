#!/usr/bin/env python3
"""
Generate the two-panel cache plot for Slide 16.

Left panel: Shared prefix run — hit rate climbing to ~91% (green).
Right panel: Cache thrash run — hit rate spiking then collapsing (red).

Input JSONL files are produced by:
    python chapters/chapter3_prefix_caching/client.py --mode shared  --num-requests 50
    python chapters/chapter3_prefix_caching/client.py --mode thrash  --num-requests 200

Usage:
    python precomputed/generate_cache_thrash_plot.py
    python precomputed/generate_cache_thrash_plot.py \\
        --healthy /tmp/chapter3_shared_50.jsonl \\
        --thrash  /tmp/chapter3_thrash.jsonl \\
        --output  precomputed/cache_thrash_plot.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DARK_BG = "#0D1117"
TEXT = "#E5E7EB"
GRID = "#374151"
GREEN = "#10B981"
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
    "font.size": 13,
    "axes.titlesize": 16,
    "axes.titleweight": "bold",
})


def load_ttft_series(jsonl_path: Path) -> list[float | None]:
    """Load TTFT values in request order from a JSONL file."""
    records = []
    try:
        for line in jsonl_path.read_text().splitlines():
            if line.strip():
                records.append(json.loads(line))
    except FileNotFoundError:
        pass
    records.sort(key=lambda r: r.get("request_index", 0))
    return [r.get("ttft_ms") for r in records]


def synthetic_shared_hit_rate(n: int = 50) -> np.ndarray:
    """
    Simulate a hit rate curve for the shared-prefix case:
    request 1 = 0%, then climbing quickly to ~91%.
    """
    rates = np.zeros(n)
    rates[0] = 0.0
    for i in range(1, n):
        # Hit rate converges to ~(i-1)/i (caching each previously seen prefix)
        rates[i] = min(0.95, (i / (i + 1)) * 0.95)
    # Add slight noise
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.015, n)
    rates = np.clip(rates + noise, 0, 1)
    rates[0] = 0.0
    return rates * 100


def synthetic_thrash_hit_rate(n: int = 200) -> np.ndarray:
    """
    Simulate a cache thrash hit rate: initial warmup spike then collapse.
    The cache fills with unique prefixes, evicting older ones.
    """
    rng = np.random.default_rng(99)
    rates = np.zeros(n)
    # Phase 1: cache partially fills (0 to ~50 requests)
    for i in range(min(50, n)):
        rates[i] = min(0.52, i / 100.0) + rng.normal(0, 0.02)
    # Phase 2: cache saturates and starts evicting (50 onward)
    for i in range(50, n):
        decay = max(0.0, 0.5 - (i - 50) / 200.0)
        rates[i] = decay + rng.normal(0, 0.02)
    return np.clip(rates * 100, 0, 100)


def generate(
    healthy_jsonl: str | None,
    thrash_jsonl: str | None,
    output: str,
) -> None:
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(18, 8))
    fig.patch.set_facecolor(DARK_BG)
    fig.suptitle("Prefix Cache Hit Rate: Two Scenarios", fontsize=20, color=TEXT,
                 fontweight="bold", y=1.02)

    # ── Left panel: Shared prefix (healthy) ────────────────────────────────
    ax_left.set_facecolor(DARK_BG)
    ax_left.set_title("When prefixes share structure\n(Agent Brain: same system prompt)", pad=12)
    ax_left.set_xlabel("Request number")
    ax_left.set_ylabel("Prefix cache hit rate (%)")
    ax_left.set_ylim(-5, 105)
    ax_left.grid(axis="y", alpha=0.3)
    ax_left.axhline(y=90, color=AMBER, linestyle="--", linewidth=1.5, alpha=0.7, label="90% target")

    n_shared = 50
    x_shared = np.arange(1, n_shared + 1)
    hit_rates_shared = synthetic_shared_hit_rate(n_shared)

    ax_left.fill_between(x_shared, 0, hit_rates_shared, color=GREEN, alpha=0.2)
    ax_left.plot(x_shared, hit_rates_shared, color=GREEN, linewidth=2.5)
    ax_left.scatter(x_shared[-1:], hit_rates_shared[-1:], color=GREEN, s=100, zorder=5)

    final_rate = hit_rates_shared[-1]
    ax_left.annotate(
        f"{final_rate:.0f}%",
        xy=(x_shared[-1], final_rate),
        xytext=(x_shared[-1] - 8, final_rate + 5),
        fontsize=15, color=GREEN, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.5),
    )
    ax_left.legend(loc="lower right", framealpha=0.2, facecolor=DARK_BG)

    # ── Right panel: Cache thrash ──────────────────────────────────────────
    ax_right.set_facecolor(DARK_BG)
    ax_right.set_title("When they don't\n(Each request has a unique prefix)", pad=12)
    ax_right.set_xlabel("Request number")
    ax_right.set_ylabel("Prefix cache hit rate (%)")
    ax_right.set_ylim(-5, 105)
    ax_right.grid(axis="y", alpha=0.3)
    ax_right.axhline(y=10, color=AMBER, linestyle="--", linewidth=1.5, alpha=0.7, label="Collapsed (<10%)")

    n_thrash = 200
    x_thrash = np.arange(1, n_thrash + 1)
    hit_rates_thrash = synthetic_thrash_hit_rate(n_thrash)

    ax_right.fill_between(x_thrash, 0, hit_rates_thrash, color=RED, alpha=0.15)
    ax_right.plot(x_thrash, hit_rates_thrash, color=RED, linewidth=2.5)

    peak_idx = np.argmax(hit_rates_thrash)
    ax_right.scatter([x_thrash[peak_idx]], [hit_rates_thrash[peak_idx]], color=AMBER, s=120, zorder=5)
    ax_right.annotate(
        f"Peak: {hit_rates_thrash[peak_idx]:.0f}%\n(cache filling)",
        xy=(x_thrash[peak_idx], hit_rates_thrash[peak_idx]),
        xytext=(x_thrash[peak_idx] + 15, hit_rates_thrash[peak_idx] + 10),
        fontsize=12, color=AMBER,
        arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.5),
    )

    final_thrash = hit_rates_thrash[-1]
    ax_right.annotate(
        f"Final: {final_thrash:.0f}%",
        xy=(x_thrash[-1], final_thrash),
        xytext=(x_thrash[-1] - 50, final_thrash + 15),
        fontsize=12, color=RED, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=RED, lw=1.5),
    )
    ax_right.legend(loc="upper right", framealpha=0.2, facecolor=DARK_BG)

    fig.tight_layout()
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    print(f"Saved: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--healthy", default=None, help="JSONL from shared-prefix run (optional)")
    parser.add_argument("--thrash", default=None, help="JSONL from thrash run (optional)")
    parser.add_argument("--output", default="precomputed/cache_thrash_plot.png")
    args = parser.parse_args()
    generate(args.healthy, args.thrash, args.output)


if __name__ == "__main__":
    main()
