# NimbusAI Webinar Runbook

> **Talk:** vLLM as an Enterprise Serving System  
> **Duration:** 60 minutes  
> **Hardware:** RunPod A100 80GB (`runpod-torch-v240`)  
> **Model:** `Qwen/Qwen2.5-7B-Instruct`

---

## Quick-reference: SSH tunnel

Open this on your laptop **before** the talk and leave it running:

```bash
ssh -L 3000:localhost:3000 root@<pod-ip> -p <pod-ssh-port> -N
```

Then open Grafana at **http://localhost:3000** on your laptop (login: `admin` / `admin`).

---

## T-60 min — Environment setup

```bash
# SSH into RunPod pod
ssh root@<pod-ip> -p <pod-ssh-port>
cd /workspace/vllm_demo

# One-time setup (skip if already done)
bash runpod/setup.sh

# Start monitoring stack
bash runpod/start_monitoring.sh
```

Verify Grafana loads at `https://<pod-id>-3000.proxy.runpod.net` or via your SSH tunnel.

---

## T-30 min — Chapter 1 server + background traffic

```bash
# Terminal 1 — Start Chapter 1 server
python scripts/webinar_orchestrator.py start --chapter 1
# Wait for: "[ok] Chapter 1 ready. Active port: 8000"

# Terminal 2 — Start background traffic (keep running)
python scripts/background_traffic.py &
# Verify Grafana panels show activity
```

---

## T-15 min — Final checks

- [ ] Grafana dashboard at `http://localhost:3000` is visible on your laptop
- [ ] All 5 panels show recent data (Running/Waiting requests, KV cache, etc.)
- [ ] Terminal with Chapter 1 demo commands is pre-typed (don't execute yet)
- [ ] Slide deck open in presentation mode
- [ ] Screen-share configured (slides ↔ Grafana ↔ terminal)
- [ ] Backup videos ready in `precomputed/backup_videos/`

---

## During the talk

### Slide 9 — Introduce the Dashboard
Switch to Grafana. The background traffic keeps it alive. Narrate the five panels.

---

### Chapter 1 — Continuous Batching (Slides 4-7)

**Setup before demo (Terminal 3):**
```bash
# Start Gantt chart — split mode showing both runs side by side
python scripts/live_gantt.py --split \
    --left /tmp/chapter1_serial.jsonl --left-title "Serial Dispatch" \
    --right /tmp/chapter1_concurrent.jsonl --right-title "Concurrent Dispatch"
```

**Live demo sequence:**
```bash
# Run serial first (~22s):
python chapters/chapter1_continuous_batching/client.py --mode serial

# Immediately after serial finishes, run concurrent (~3s):
python chapters/chapter1_continuous_batching/client.py --mode concurrent
```

**What audience sees:** Gantt chart builds up serialized bars on the left (one at a time), then concurrent bars all together on the right (overlapping, ~7x faster).

**If demo fails:** Play `precomputed/backup_videos/chapter1_demo.mp4`

---

### Chapter 2 — Chunked Prefill (Slides 8-12)

**Transition (after Chapter 1 chapter card — ~25 seconds to narrate):**
```bash
# Switch servers (stops ch1 server, starts ch2 servers)
python scripts/webinar_orchestrator.py switch --chapter 2
# Wait for "[ok] Chapter 2 ready. Active port: 8000. All ports: [8000, 8001]"
```

**Demo — Part A (chunked prefill OFF, port 8000):**
```bash
python chapters/chapter2_noisy_neighbor/client.py --port 8000
```
Watch TTFT spike on Grafana Panel 4 (TTFT Histogram) at T=10s.

**Demo — Part B (chunked prefill ON, port 8001):**
```bash
python chapters/chapter2_noisy_neighbor/client.py --port 8001
```
TTFT stays flat despite the Legal injection.

**If demo fails:** Play `precomputed/backup_videos/chapter2_demo.mp4`

---

### Chapter 3 — Prefix Caching (Slides 13-16)

**Transition:**
```bash
python scripts/webinar_orchestrator.py switch --chapter 3
# Wait for "[ok] Chapter 3 ready. Active port: 8002. All ports: [8002, 8003]"
```

**Demo 3.1 — Live (Slide 15):**
```bash
# Without caching (port 8002) — every request ~800ms:
python chapters/chapter3_prefix_caching/client.py --port 8002 --mode shared --num-requests 10

# With caching (port 8003) — requests 2-10 ~140ms:
python chapters/chapter3_prefix_caching/client.py --port 8003 --mode shared --num-requests 10
```
Watch Panel 3 (Prefix Cache Hit Rate) climb from 0% to ~91% during the second run.

**Demo 3.2 — Pre-generated chart (Slide 16):**
Switch to the `precomputed/cache_thrash_plot.png` image (embed in slide or open separately).

**If demo fails:** Play `precomputed/backup_videos/chapter3_demo.mp4`

---

### Chapter 4 — SLO + Cost (Slides 17-19)

No live demo. Show the pre-generated capacity table from `precomputed/capacity_table.json` embedded in Slide 19.

**No server transition needed.** Just present slides 17-19.

---

### Chapter 5 — PagedAttention + KV Cache (Slides 20-23)

**Transition:**
```bash
python scripts/webinar_orchestrator.py switch --chapter 5
# Wait for "[ok] Chapter 5 ready. Active port: 8004. All ports: [8004, 8005]"
```

**Demo — High utilization (port 8004, gpu-mem-util 0.95):**
```bash
python chapters/chapter5_kv_pressure/client.py --port 8004
```
Watch Panel 2 (KV Cache) climb toward 95%. Watch Panel 6 (Preemptions) increment.

**Demo — Lower utilization (port 8005, gpu-mem-util 0.85):**
```bash
python chapters/chapter5_kv_pressure/client.py --port 8005
```
KV cache stays under 90%. Preemptions stay at 0.

**If demo fails:** Play `precomputed/backup_videos/chapter5_demo.mp4`

---

### Chapter 6 — Speculative Decoding (Slides 24-25)

No live demo. Show `precomputed/speculative_decoding_chart.png` (embedded in Slide 25).

**Transition (end of talk):**
```bash
python scripts/webinar_orchestrator.py stop
```

---

## Post-talk cleanup

```bash
# Stop background traffic (if it's still running)
kill %1   # or find and kill the background_traffic.py process

# Stop all servers
python scripts/webinar_orchestrator.py stop

# Stop monitoring
bash runpod/stop_monitoring.sh

# Optional: pause the RunPod pod to stop billing
# (do this from the RunPod web console)
```

---

## Failure modes and recovery

### vLLM server won't start
```bash
# Check what's on the port
lsof -i :<port>
# Check server log
tail -100 /tmp/vllm_port<port>.log
# Nuclear option: kill all vllm processes
pkill -f "vllm serve"
# Then restart
python scripts/webinar_orchestrator.py stop
python scripts/webinar_orchestrator.py start --chapter <N>
```

### Grafana dashboard goes blank
```bash
# Check Prometheus is alive
curl http://localhost:9090/api/v1/query?query=up
# Restart if needed
bash runpod/stop_monitoring.sh && bash runpod/start_monitoring.sh
```

### Prefix cache hit rate panel shows 0% when it should be climbing
- vLLM may not expose `vllm:gpu_prefix_cache_*_total` on older versions.
- Check: `curl -s http://localhost:8003/metrics | grep prefix_cache`
- If missing, narrate the expected behavior from memory.

### Demo numbers look wrong (TTFT too slow or not enough contrast)
- Switch to backup video without explanation.
- Audience won't notice — they're watching the screen, not the clock.

### SSH tunnel drops mid-talk
```bash
# Re-establish tunnel from another laptop terminal
ssh -L 3000:localhost:3000 root@<pod-ip> -p <pod-ssh-port> -N
# Refresh Grafana in browser
```

---

## Pre-generation checklist (run 1-2 days before the webinar)

```bash
# 1. Generate legal contract (if not already done)
python chapters/chapter2_noisy_neighbor/generate_contract.py

# 2. Generate cache thrash plot (Slide 16)
python precomputed/generate_cache_thrash_plot.py

# 3. Generate speculative decoding chart (Slide 25)
#    Option A: Use demo data (already generated, ~60s)
python precomputed/generate_speculative_chart.py
#    Option B: Run real benchmark (~6 min, requires 2 servers)
python chapters/chapter6_speculative_decoding/benchmark.py && \
python precomputed/generate_speculative_chart.py

# 4. Generate capacity table (Slide 19) — 60-120 min, requires manual steps
python chapters/chapter4_capacity_planning/sweep.py --all-configs \
    --hourly-rate 2.50 --slo-p95-ttft 500

# 5. Record backup videos (during rehearsal)
# Use OBS Studio on your laptop with screen capture
# One video per live demo chapter (~2-3 min each)
# Save to precomputed/backup_videos/chapter{1,2,3,5}_demo.mp4
```

---

## Rehearsal protocol

Run at least **2 full rehearsals** before the webinar day:

1. **Dry run 1 (2 days before):** End-to-end walkthrough. Identify timing issues. Generate backup videos.
2. **Dry run 2 (1 day before):** Presentation-mode run. Practice Grafana ↔ slide switching. Verify all demos hit expected numbers.

Each rehearsal should take ~75 minutes (60 min talk + 15 min setup/teardown).

**Note:** At ~$1.89/hr RunPod pricing, each rehearsal costs ~$2.50. Total demo budget: ~$20-30.
