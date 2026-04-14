# vLLM Systems Demo: Continuous Batching, Chunked Prefill, PagedAttention, and Prefix Caching

This mini-project gives you a **runnable demo setup** for showing how vLLM behaves under realistic serving workloads.

The demo is built around:
- **vLLM OpenAI-compatible server**
- **Custom async client** for controlled request arrival patterns
- **Metrics scraping** from `http://<host>:8000/metrics`
- **Matplotlib plots** for professor-friendly visuals
- **Optional Prometheus + Grafana** local monitoring stack

## What this demo proves

1. **Continuous batching**
   - Mixed request lengths under serialized arrivals vs concurrent arrivals.
   - Visualized using a Gantt-style request timeline.

2. **Chunked prefill**
   - A long prompt is injected while short requests continue arriving.
   - Compare runs from two server configs:
     - `--no-enable-chunked-prefill`
     - default / `--enable-chunked-prefill`
   - Visualized using ITL and TTFT changes for short requests.

3. **Prefix caching**
   - Reuse the same long system prefix across repeated requests.
   - Compare:
     - `--no-enable-prefix-caching`
     - `--enable-prefix-caching`
   - Visualized using TTFT per request index.

4. **PagedAttention / concurrency scaling proxy**
   - Run a concurrency sweep and observe throughput / tail latency.
   - We do **not** intentionally crash the system. Instead, we show where performance degrades as concurrency rises.

## Current vLLM behavior you should know

- In vLLM V1, **chunked prefill is enabled by default whenever possible**.
- With chunked prefill enabled, vLLM prioritizes decode requests and schedules prefills into the remaining `max_num_batched_tokens` budget.
- vLLM exposes Prometheus metrics on the `/metrics` endpoint.
- Automatic Prefix Caching only speeds up the **prefill** part, not the decoding of newly generated tokens.

## Recommended project layout

```text
vllm_demo/
  README.md
  requirements.txt
  scripts/
    client_benchmark.py
    analyze_results.py
    scrape_metrics.py
  configs/
    prometheus.yml
    docker-compose.metrics.yml
  examples/
    server_profiles.sh
    run_demo_sequence.sh
  results/
```

## 1) Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You also need vLLM installed in the environment where you run the server.

## 2) Start a vLLM server

Pick one instruct model that fits your GPU. Then launch one of the profiles in `examples/server_profiles.sh`.

Example:

```bash
vllm serve <your-instruct-model> \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --max-num-batched-tokens 4096
```

## 3) Quick smoke test

```bash
python scripts/client_benchmark.py \
  --base-url http://localhost:8000/v1 \
  --model <your-instruct-model> \
  --scenario mixed_batching \
  --label smoke \
  --output-root results
```

## 4) Demo scenarios

### A. Continuous batching

#### Serialized baseline
```bash
python scripts/client_benchmark.py \
  --base-url http://localhost:8000/v1 \
  --model <your-instruct-model> \
  --scenario mixed_batching \
  --serialized \
  --label serialized \
  --output-root results
```

#### Concurrent vLLM serving
```bash
python scripts/client_benchmark.py \
  --base-url http://localhost:8000/v1 \
  --model <your-instruct-model> \
  --scenario mixed_batching \
  --request-rate 2.5 \
  --label vllm_concurrent \
  --output-root results
```

### B. Chunked prefill

Run the same workload twice: once on a server with `--no-enable-chunked-prefill`, once on the default server.

```bash
python scripts/client_benchmark.py \
  --base-url http://localhost:8000/v1 \
  --model <your-instruct-model> \
  --scenario chunked_prefill \
  --short-request-count 20 \
  --request-rate 1.5 \
  --long-prompt-repeat 5000 \
  --label no_chunked_or_default \
  --output-root results
```

### C. Prefix caching

Run twice: prefix caching disabled, then enabled.

```bash
python scripts/client_benchmark.py \
  --base-url http://localhost:8000/v1 \
  --model <your-instruct-model> \
  --scenario prefix_cache \
  --prefix-repeat 2500 \
  --prefix-query-count 8 \
  --label prefix_cache_run \
  --output-root results
```

### D. Concurrency sweep

```bash
python scripts/client_benchmark.py \
  --base-url http://localhost:8000/v1 \
  --model <your-instruct-model> \
  --scenario sweep \
  --sweep-values 1,2,4,8,12,16 \
  --requests-per-sweep 12 \
  --label sweep \
  --output-root results
```

## 5) Scrape raw metrics

Before or after a run:

```bash
python scripts/scrape_metrics.py \
  --metrics-url http://localhost:8000/metrics \
  --output results/metrics_snapshot.prom
```

## 6) Generate professor-friendly plots

```bash
python scripts/analyze_results.py \
  --results-root results \
  --output-dir results/plots
```

This generates:
- `gantt_mixed_batching.png`
- `chunked_prefill_itl.png`
- `prefix_cache_ttft.png`
- `concurrency_sweep.png`

## Practical notes

- Use **short outputs** for prefix cache experiments. Prefix caching accelerates prefill, not long generations.
- For chunked prefill, use a **very long prompt** and many **short interactive prompts**.
- For concurrency sweep, keep the prompt size and output length fixed so comparisons are fair.
- If you disable chunked prefill, ensure `max_num_batched_tokens > max_model_len` or server startup may fail.

## Optional: Prometheus + Grafana

A local starter config is provided in `configs/`.

```bash
cd configs
docker compose -f docker-compose.metrics.yml up -d
```

Then:
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

