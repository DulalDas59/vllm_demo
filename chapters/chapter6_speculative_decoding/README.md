# Chapter 6 — Speculative Decoding Benchmark

## What this produces
Bar chart for Slide 25 showing throughput ratios at c=1, c=4, c=16 (with vs without spec decoding).

## Servers needed (start both before running)

```bash
# Standard server (no speculative decoding)
bash configs/vllm_servers/chapter1_default.sh   # port 8000

# Speculative decoding server (ngram method, no draft model)
vllm serve "Qwen/Qwen2.5-7B-Instruct" \
  --host 0.0.0.0 --port 8006 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --speculative-config '{"method": "ngram", "num_speculative_tokens": 4, "prompt_lookup_max": 4}' \
  --disable-log-requests
```

Note: Both servers can run concurrently on 80GB A100 if you reduce gpu-memory-utilization to ~0.44 each.

## Run benchmark

```bash
python chapters/chapter6_speculative_decoding/benchmark.py \
    --port-baseline 8000 --port-spec 8006 \
    --output precomputed/speculative_results.json
```

Total runtime: ~6 minutes (3 concurrency levels × 60s × 2 runs each).

## Generate chart

```bash
python precomputed/generate_speculative_chart.py
```

## Expected ratios
- c=1: ~1.4-1.8x (speculation helps at low concurrency)
- c=4: ~0.95-1.15x (roughly neutral)
- c=16: ~0.75-0.95x (speculation hurts at high concurrency — overhead dominates)
