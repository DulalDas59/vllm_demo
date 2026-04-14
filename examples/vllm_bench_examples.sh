#!/usr/bin/env bash
# Optional built-in vLLM benchmark examples.
# These use vLLM's own bench CLI to produce percentile metrics and optional timeline plots.

BASE_URL="${BASE_URL:-http://localhost:8000}"
MODEL="${MODEL:-YOUR_MODEL_NAME}"

# Random synthetic load with Poisson arrivals.
vllm bench serve   --backend openai-chat   --base-url "$BASE_URL"   --endpoint /v1/chat/completions   --model "$MODEL"   --dataset-name random   --random-input-len 512   --random-output-len 64   --num-prompts 40   --request-rate 2.0   --percentile-metrics ttft,tpot,itl,e2el   --metric-percentiles 50,95,99   --plot-timeline   --save-result   --result-dir results
