#!/bin/bash
# Chapter 5 — KV Cache Pressure (gpu-memory-utilization 0.85)
# Lower utilization: KV cache stays under 90%, zero preemptions, slightly lower throughput.
MODEL="Qwen/Qwen2.5-7B-Instruct"
exec vllm serve "$MODEL" \
  --host 0.0.0.0 \
  --port 8005 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.85 \
  --enable-chunked-prefill \
  --max-num-batched-tokens 4096 \
  --disable-log-requests
