#!/bin/bash
# Chapter 3 — Prefix Caching (caching DISABLED)
# Without prefix caching: every agent request pays full 3600-token prefill cost.
MODEL="Qwen/Qwen2.5-7B-Instruct"
exec vllm serve "$MODEL" \
  --host 0.0.0.0 \
  --port 8002 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --no-enable-prefix-caching \
  --max-num-batched-tokens 4096 \
  --disable-log-requests
