from __future__ import annotations

import argparse
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape vLLM Prometheus metrics and save the raw exposition text.")
    parser.add_argument("--metrics-url", default="http://localhost:8000/metrics")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    response = requests.get(args.metrics_url, timeout=30)
    response.raise_for_status()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(response.text, encoding="utf-8")
    print(f"Saved metrics snapshot to: {output}")


if __name__ == "__main__":
    main()
