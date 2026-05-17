# Chapter 1 — Continuous Batching Demo

## What this proves
Serial dispatch (one request at a time) vs concurrent dispatch (all at once) against the same vLLM server. Target: 5-7x wall time ratio.

## Server
```bash
bash configs/vllm_servers/chapter1_default.sh
```

## Demo commands

### Terminal 1 — Start Gantt chart (split mode)
```bash
python scripts/live_gantt.py --split \
    --left /tmp/chapter1_serial.jsonl --left-title "Serial Dispatch" \
    --right /tmp/chapter1_concurrent.jsonl --right-title "Concurrent Dispatch"
```

### Terminal 2 — Run serial first, then concurrent
```bash
# Serial (~22s)
python chapters/chapter1_continuous_batching/client.py --mode serial

# Then concurrent (~3s)
python chapters/chapter1_continuous_batching/client.py --mode concurrent
```

## Expected output
- Serial: ~20-25s wall time, bars are sequential (no overlap)
- Concurrent: ~2-4s wall time, bars all start and end overlapping
- Ratio: 5-7x
