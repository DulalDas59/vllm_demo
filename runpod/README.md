# RunPod Operational Scripts

## First time setup

```bash
bash runpod/setup.sh
```

Installs Prometheus, Grafana, vLLM, Python deps, and pre-downloads the model (~15GB).

## Day of webinar

```bash
bash runpod/start_monitoring.sh
```

Starts Prometheus (port 9090) and Grafana (port 3000). Access Grafana at:
```
https://<pod-id>-3000.proxy.runpod.net
```
Login: `admin` / `admin`.

## Stop monitoring

```bash
bash runpod/stop_monitoring.sh
```

## Pre-download model only

```bash
bash runpod/prefetch_model.sh
```

## Make scripts executable

```bash
chmod +x runpod/*.sh configs/vllm_servers/*.sh
```
