#!/bin/bash
# Pre-download Qwen2.5-7B-Instruct to /workspace/models.
# Run this once before the webinar to avoid download time during demos.

set -euo pipefail

MODEL_ID="Qwen/Qwen2.5-7B-Instruct"
LOCAL_DIR="/workspace/models/Qwen2.5-7B-Instruct"

if [ -d "${LOCAL_DIR}" ] && [ -f "${LOCAL_DIR}/config.json" ]; then
    echo "[ok] Model already downloaded at ${LOCAL_DIR}"
    du -sh "${LOCAL_DIR}"
    exit 0
fi

echo "Downloading ${MODEL_ID}..."
echo "This will take 5-10 minutes (~15GB)."
echo ""

huggingface-cli download "${MODEL_ID}" \
    --local-dir "${LOCAL_DIR}"

echo ""
echo "[ok] Model downloaded to ${LOCAL_DIR}"
du -sh "${LOCAL_DIR}"
echo ""
echo "Set HF_HOME or pass --model path to vllm serve to use local weights."
echo "The server scripts in configs/vllm_servers/ use the HF model ID directly;"
echo "HuggingFace caches the weights automatically if HF_HUB_CACHE is set."
