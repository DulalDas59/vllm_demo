# Chapter 3 — Prefix Caching Demo

## What this proves
Agent Brain sends 50K calls/day with a 3,600-token shared prefix. Prefix caching reuses the KV state, cutting TTFT from ~800ms to ~140ms for requests 2-10.

## Servers (restart between configs)
```bash
# Without prefix caching:
bash configs/vllm_servers/chapter3_prefix_off.sh   # port 8002

# With prefix caching:
bash configs/vllm_servers/chapter3_prefix_on.sh    # port 8003
```

## Demo 3.1 (live — Slide 15)
```bash
# Against prefix_off (every request pays full cost):
python chapters/chapter3_prefix_caching/client.py --port 8002 --mode shared --num-requests 10

# Restart server, then against prefix_on (requests 2-10 are ~5x faster):
python chapters/chapter3_prefix_caching/client.py --port 8003 --mode shared --num-requests 10
```

## Demo 3.2 (offline — generates Slide 16 data)
```bash
# Against prefix_on with UNIQUE prefixes (shows cache thrashing):
python chapters/chapter3_prefix_caching/client.py --port 8003 --mode thrash --num-requests 200
# Then generate the plot:
python precomputed/generate_cache_thrash_plot.py
```

## Expected output (shared mode against prefix_on)
- Request 1: ~700-900ms TTFT
- Requests 2-10: ~120-180ms TTFT (~5x improvement)
- Grafana Panel 3 (Prefix Cache Hit Rate): climbs to >85%
