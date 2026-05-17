#!/bin/bash
# Chapter 2 — Noisy Neighbor (chunked prefill ENABLED)
# With chunked prefill: HelpDesk TTFT stays stable despite Legal Titan injection.
MODEL="Qwen/Qwen2.5-7B-Instruct"
exec vllm serve "$MODEL" \
  --host 0.0.0.0 \
  --port 8001 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.90 \
  --enable-chunked-prefill \
  --max-num-batched-tokens 4096 \
  --max-num-partial-prefills 2 \
  --long-prefill-token-threshold 1024 \
  --disable-log-requests
