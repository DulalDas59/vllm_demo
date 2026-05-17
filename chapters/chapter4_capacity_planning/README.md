# Chapter 4 — Capacity Planning (No Live Demo)

## What this produces
A JSON table used in Slide 19. Four configurations with p95 TTFT, saturation rps, and cost per million output tokens.

## To generate (run before the webinar)

This requires running each vLLM server configuration sequentially. Total time: ~60-120 minutes.

```bash
# Option 1: Interactive all-configs sweep (prompts between each config)
python chapters/chapter4_capacity_planning/sweep.py --all-configs \
    --hourly-rate 2.50 --slo-p95-ttft 500 --output precomputed/capacity_table.json

# Option 2: Single config at a time
# (Start the right server, then run)
python chapters/chapter4_capacity_planning/sweep.py \
    --config baseline --port 8000 --output precomputed/capacity_table.json
```

## Output format
```json
[
  {"config": "Baseline", "p95_ttft_ms": 840, "saturation_rps": 7, "cost_per_1m_tokens": 4.20, "verdict": "Fails"},
  {"config": "+ Chunked prefill", ...},
  {"config": "+ Prefix caching", ...},
  {"config": "+ Both", ...}
]
```

## Recompute costs only
```bash
python chapters/chapter4_capacity_planning/compute_capacity_table.py --hourly-rate 1.49
```
