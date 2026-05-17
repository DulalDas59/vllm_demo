#!/bin/bash
# One-time setup script for RunPod runpod-torch-v240 template.
# Run once from /workspace/vllm_demo/ after cloning the repo.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "=== NimbusAI Webinar Setup ==="
echo "Repo: ${REPO_DIR}"

# 1. System deps
echo ""
echo "[1/6] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq wget curl tmux git

# 2. Python deps
echo ""
echo "[2/6] Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r "${REPO_DIR}/requirements.txt" --quiet

# 3. vLLM
echo ""
echo "[3/6] Installing vLLM..."
pip install vllm --quiet

# 4. Prometheus
echo ""
echo "[4/6] Installing Prometheus..."
PROM_VERSION="2.55.0"
if [ ! -f "/opt/prometheus/prometheus" ]; then
    cd /tmp
    wget -q "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
    tar -xzf "prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
    mv "prometheus-${PROM_VERSION}.linux-amd64" /opt/prometheus
    rm "prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
    echo "  Prometheus installed at /opt/prometheus"
else
    echo "  Prometheus already installed, skipping."
fi

# 5. Grafana
echo ""
echo "[5/6] Installing Grafana..."
GRAFANA_VERSION="11.3.0"
if [ ! -f "/opt/grafana/bin/grafana-server" ]; then
    cd /tmp
    wget -q "https://dl.grafana.com/oss/release/grafana-${GRAFANA_VERSION}.linux-amd64.tar.gz"
    tar -xzf "grafana-${GRAFANA_VERSION}.linux-amd64.tar.gz"
    mv "grafana-${GRAFANA_VERSION}" /opt/grafana
    rm "grafana-${GRAFANA_VERSION}.linux-amd64.tar.gz"
    echo "  Grafana installed at /opt/grafana"
else
    echo "  Grafana already installed, skipping."
fi

# Create Grafana data dirs
mkdir -p /opt/grafana/data/dashboards
cp "${REPO_DIR}/configs/grafana/dashboards/nimbusai_control_room.json" \
   /opt/grafana/data/dashboards/nimbusai_control_room.json

# 6. Pre-download model
echo ""
echo "[6/6] Pre-downloading Qwen/Qwen2.5-7B-Instruct..."
echo "  This will take 5-10 minutes (~15GB download)..."
huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
    --local-dir /workspace/models/Qwen2.5-7B-Instruct \
    --quiet
echo "  Model downloaded to /workspace/models/Qwen2.5-7B-Instruct"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. bash runpod/start_monitoring.sh"
echo "  2. python scripts/webinar_orchestrator.py start --chapter 1"
echo "  3. python scripts/background_traffic.py &"
