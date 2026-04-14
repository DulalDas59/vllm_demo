#!/usr/bin/env bash
# Example server launch profiles.
# Replace <MODEL> with your actual instruct model.

# Profile 1: Default server for continuous batching and general tests.
vllm serve <MODEL> \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --max-num-batched-tokens 4096

# Profile 2: Disable chunked prefill for A/B comparison.
# NOTE: when chunked prefill is disabled, keep max-num-batched-tokens > max-model-len.
vllm serve <MODEL> \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --no-enable-chunked-prefill \
  --max-num-batched-tokens 12288

# Profile 3: Chunked prefill tuned for mixed workloads.
vllm serve <MODEL> \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --enable-chunked-prefill \
  --max-num-batched-tokens 4096 \
  --max-num-partial-prefills 2 \
  --max-long-partial-prefills 1 \
  --long-prefill-token-threshold 1024

# Profile 4: Prefix caching disabled.
vllm serve <MODEL> \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --no-enable-prefix-caching

# Profile 5: Prefix caching enabled.
vllm serve <MODEL> \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --enable-prefix-caching
