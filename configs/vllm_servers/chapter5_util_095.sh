#!/bin/bash
# Chapter 5 — KV Cache Pressure (gpu-memory-utilization 0.95)
# High utilization: KV cache climbs to 95%+, preemptions occur under heavy load.
MODEL="Qwen/Qwen2.5-7B-Instruct"
exec vllm serve "$MODEL" \
  --host 0.0.0.0 \
  --port 8004 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.95 \
  --enable-chunked-prefill \
  --max-num-batched-tokens 4096 \
  --disable-log-requests
