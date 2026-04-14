#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000/v1}"
MODEL="${MODEL:-YOUR_MODEL_NAME}"
OUT="${OUT:-results}"

python scripts/client_benchmark.py --base-url "$BASE_URL" --model "$MODEL" --scenario mixed_batching --serialized --label serialized --output-root "$OUT"
python scripts/client_benchmark.py --base-url "$BASE_URL" --model "$MODEL" --scenario mixed_batching --request-rate 2.5 --label vllm_concurrent --output-root "$OUT"

# Restart server as needed between the following runs.
python scripts/client_benchmark.py --base-url "$BASE_URL" --model "$MODEL" --scenario chunked_prefill --short-request-count 20 --request-rate 1.5 --long-prompt-repeat 5000 --label chunked_prefill_ab --output-root "$OUT"
python scripts/client_benchmark.py --base-url "$BASE_URL" --model "$MODEL" --scenario prefix_cache --prefix-repeat 2500 --prefix-query-count 8 --label prefix_cache_ab --output-root "$OUT"
python scripts/client_benchmark.py --base-url "$BASE_URL" --model "$MODEL" --scenario sweep --sweep-values 1,2,4,8,12,16 --requests-per-sweep 12 --label sweep --output-root "$OUT"

python scripts/analyze_results.py --results-root "$OUT" --output-dir "$OUT/plots"
