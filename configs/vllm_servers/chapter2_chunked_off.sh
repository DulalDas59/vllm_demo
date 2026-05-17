#!/bin/bash
# Chapter 2 — Noisy Neighbor (chunked prefill DISABLED)
# Without chunked prefill: Legal Titan's 30K prefill blocks HelpDesk TTFT.
MODEL="Qwen/Qwen2.5-7B-Instruct"
exec vllm serve "$MODEL" \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.90 \
  --no-enable-chunked-prefill \
  --max-num-batched-tokens 32768 \
  --disable-log-requests
