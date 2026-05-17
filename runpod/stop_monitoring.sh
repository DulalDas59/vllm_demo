#!/bin/bash
# Stop Prometheus and Grafana.

for SERVICE in prometheus grafana; do
    PID_FILE="/tmp/${SERVICE}.pid"
    if [ -f "${PID_FILE}" ]; then
        PID=$(cat "${PID_FILE}")
        if kill -0 "${PID}" 2>/dev/null; then
            kill "${PID}"
            echo "[ok] ${SERVICE} stopped (PID ${PID})"
        else
            echo "[warn] ${SERVICE} was not running (stale PID file)"
        fi
        rm -f "${PID_FILE}"
    else
        echo "[info] ${SERVICE} not running"
    fi
done
