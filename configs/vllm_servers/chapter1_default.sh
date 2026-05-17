#!/bin/bash
# Chapter 1 — Continuous Batching demo
# Default config. One server, port 8000.
MODEL="Qwen/Qwen2.5-7B-Instruct"
exec vllm serve "$MODEL" \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --max-num-batched-tokens 4096 \
  --disable-log-requests
