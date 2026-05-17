#!/usr/bin/env python3
"""
Standalone capacity table cost calculator.

Given measured saturation rps values, computes $/1M output tokens
and prints a formatted table.

Usage:
    python chapters/chapter4_capacity_planning/compute_capacity_table.py
    python chapters/chapter4_capacity_planning/compute_capacity_table.py \\
        --input precomputed/capacity_table.json --hourly-rate 2.50
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def cost_per_1m(sat_rps: float, hourly_rate: float, avg_output_tokens: int = 50) -> float:
    if sat_rps <= 0:
        return 0.0
    tokens_per_hour = sat_rps * avg_output_tokens * 3600
    return round((hourly_rate * 1_000_000) / tokens_per_hour, 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="precomputed/capacity_table.json")
    parser.add_argument("--hourly-rate", type=float, default=2.50)
    parser.add_argument("--avg-output-tokens", type=int, default=50)
    args = parser.parse_args()

    p = Path(args.input)
    if not p.exists():
        print(f"Input file not found: {p}")
        print("Run sweep.py first to generate measurements.")
        return

    rows = json.loads(p.read_text())

    print(f"\n{'Config':<25} {'p95 TTFT':>10} {'Sat rps':>8} {'$/1M tok':>10} {'Verdict':>8}")
    print("-" * 70)
    for row in rows:
        p95 = f"{row.get('p95_ttft_ms', '?')}ms"
        sat = row.get("saturation_rps", 0)
        c = cost_per_1m(sat, args.hourly_rate, args.avg_output_tokens)
        row["cost_per_1m_tokens"] = c
        verdict = row.get("verdict", "?")
        print(f"  {row['config']:<23} {p95:>10} {sat:>8.0f} {c:>10.2f} {verdict:>8}")

    print("")
    p.write_text(json.dumps(rows, indent=2))
    print(f"Updated cost figures written to {p}")


if __name__ == "__main__":
    main()
