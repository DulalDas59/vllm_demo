#!/bin/bash
# Start Prometheus and Grafana monitoring stack.
# Safe to call multiple times — checks if already running.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Prometheus ────────────────────────────────────────────────────────────────
if [ -f /tmp/prometheus.pid ] && kill -0 "$(cat /tmp/prometheus.pid)" 2>/dev/null; then
    echo "[ok] Prometheus already running (PID $(cat /tmp/prometheus.pid))"
else
    echo "Starting Prometheus..."
    mkdir -p /tmp/prometheus-data
    nohup /opt/prometheus/prometheus \
        --config.file="${REPO_DIR}/configs/prometheus.yml" \
        --storage.tsdb.path=/tmp/prometheus-data \
        --web.listen-address=:9090 \
        > /tmp/prometheus.log 2>&1 &
    echo $! > /tmp/prometheus.pid
    sleep 2
    if kill -0 "$(cat /tmp/prometheus.pid)" 2>/dev/null; then
        echo "[ok] Prometheus started (PID $(cat /tmp/prometheus.pid))"
    else
        echo "[ERROR] Prometheus failed to start. Check /tmp/prometheus.log"
        exit 1
    fi
fi

# ── Grafana ───────────────────────────────────────────────────────────────────
# Ensure dashboard is up to date
mkdir -p /opt/grafana/data/dashboards
cp "${REPO_DIR}/configs/grafana/dashboards/nimbusai_control_room.json" \
   /opt/grafana/data/dashboards/nimbusai_control_room.json

if [ -f /tmp/grafana.pid ] && kill -0 "$(cat /tmp/grafana.pid)" 2>/dev/null; then
    echo "[ok] Grafana already running (PID $(cat /tmp/grafana.pid))"
else
    echo "Starting Grafana..."
    nohup /opt/grafana/bin/grafana-server \
        --homepath=/opt/grafana \
        --config="${REPO_DIR}/configs/grafana/grafana.ini" \
        > /tmp/grafana.log 2>&1 &
    echo $! > /tmp/grafana.pid
    sleep 4
    if kill -0 "$(cat /tmp/grafana.pid)" 2>/dev/null; then
        echo "[ok] Grafana started (PID $(cat /tmp/grafana.pid))"
    else
        echo "[ERROR] Grafana failed to start. Check /tmp/grafana.log"
        exit 1
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
POD_ID="${RUNPOD_POD_ID:-<your-pod-id>}"
echo ""
echo "=== Monitoring stack ready ==="
echo "  Prometheus:  http://localhost:9090 (internal)"
echo "  Grafana:     https://${POD_ID}-3000.proxy.runpod.net"
echo "  Login:       admin / admin"
echo ""
echo "Open Grafana and confirm the 'NimbusAI · Serving Control Room' dashboard loads."
