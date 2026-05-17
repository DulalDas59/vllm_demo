#!/bin/bash
# Chapter 3 — Prefix Caching (caching ENABLED)
# With prefix caching: requests 2-10 get ~5x TTFT improvement via KV reuse.
MODEL="Qwen/Qwen2.5-7B-Instruct"
exec vllm serve "$MODEL" \
  --host 0.0.0.0 \
  --port 8003 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --enable-prefix-caching \
  --max-num-batched-tokens 4096 \
  --disable-log-requests
