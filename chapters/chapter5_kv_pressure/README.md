# Chapter 5 — KV Cache Pressure Demo

## What this proves
High gpu-memory-utilization (0.95) causes KV cache to fill, triggering preemptions.
Lower utilization (0.85) keeps headroom, zero preemptions, slightly lower peak throughput.

## Workload tuning
Default: 2000-token prompts. If KV cache doesn't reach 90%+, increase `--prompt-tokens`:
```bash
python chapters/chapter5_kv_pressure/client.py --port 8004 --prompt-tokens 3000
```

## Servers (restart between configs)
```bash
# High utilization (should trigger preemptions):
bash configs/vllm_servers/chapter5_util_095.sh   # port 8004

# Lower utilization (stable):
bash configs/vllm_servers/chapter5_util_085.sh   # port 8005
```

## Demo commands
```bash
# Against 0.95 server (shows KV pressure + preemptions):
python chapters/chapter5_kv_pressure/client.py --port 8004

# Restart server, then against 0.85 (stable):
python chapters/chapter5_kv_pressure/client.py --port 8005
```

## Expected output
- Port 8004 (0.95): KV panel hits 90%+, preemptions counter increments ≥3
- Port 8005 (0.85): KV panel stays <90%, preemptions = 0
- Throughput on 0.95 is ~5-15% higher than 0.85 at peak concurrency
