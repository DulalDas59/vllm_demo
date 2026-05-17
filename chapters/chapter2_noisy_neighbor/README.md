# Chapter 2 — Noisy Neighbor (Chunked Prefill) Demo

## What this proves
Legal Titan's 30K-token prefill blocks HelpDesk Hero's TTFT without chunked prefill.
With chunked prefill, HelpDesk TTFT stays stable.

## Pre-requisite
```bash
python chapters/chapter2_noisy_neighbor/generate_contract.py
```
Generates `legal_contract_30k.txt` (~30K tokens).

## Servers (run one at a time, Path A strategy)
```bash
# Run WITHOUT chunked prefill first:
bash configs/vllm_servers/chapter2_chunked_off.sh   # port 8000

# Then restart WITH chunked prefill:
bash configs/vllm_servers/chapter2_chunked_on.sh    # port 8001
```

## Demo commands

```bash
# Against chunked_off (shows the spike):
python chapters/chapter2_noisy_neighbor/client.py --port 8000

# Against chunked_on (shows stable TTFT):
python chapters/chapter2_noisy_neighbor/client.py --port 8001
```

## Expected output
- **Port 8000 (OFF):** HelpDesk p95 TTFT spikes from ~400ms to >5s at T=10s
- **Port 8001 (ON):** HelpDesk p95 TTFT stays under ~700ms throughout
- Grafana TTFT histogram (Panel 4) visibly shifts right in the OFF run
