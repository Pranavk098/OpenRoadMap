# Deploy: Oracle Cloud Always Free ARM (Arch B) — $0, full stack untouched

Target: one A1.Flex Ampere ARM instance (2 OCPU / 12 GB RAM, 100 GB boot),
Ubuntu 24.04 aarch64, Docker + this repo's `docker-compose.prod.yml`
(API with baked ONNX weights + Qdrant sidecar + Caddy TLS).
Full-stack RSS is ~650 MB–1 GB, so 12 GB holds everything with room for
`bge-base` restoration later. No sleep, persistent disk: models bake once,
never cold-start. Expected latency: `structure` SSE <5 s, full roadmap
~7–10 s (2 OCPU vs Render 0.1 CPU is ~20× the embedding/rerank compute).

## 0. One-time Oracle setup (~30 min, all free)

1. Register Oracle Cloud (Always Free tier, card required for verification,
   not charged). If your home region shows "out of capacity" for A1.Flex,
   retry off-peak or try a second region — the known friction point.
2. Create instance: shape `VM.Standard.A1.Flex`, 2 OCPU / 12 GB, boot
   100 GB, Ubuntu 24.04 Minimal aarch64, public subnet, paste your
   `~/.ssh/id_ed25519.pub`.
3. Security list: open ingress 80 + 443 (Caddy) and 22 (your IP only).
   Alternative that avoids public ports entirely: Cloudflare Tunnel
   (`cloudflared`) — skip opening 80/443, point DNS at the tunnel.
4. DNS: `api.<yourdomain>` → instance IP (or DuckDNS subdomain, free).

## 1. VM prep

```bash
ssh ubuntu@<ip>
sudo apt update && sudo apt install -y docker.io docker-compose-plugin caddy 2>/dev/null
sudo usermod -aG docker $USER && newgrp docker
git clone https://github.com/Pranavk098/OpenRoadMap.git && cd OpenRoadMap
cp .env.example .env   # fill in: OPENAI_API_KEY, ALLOWED_ORIGINS (Vercel URL),
                       # QDRANT_URL (Cloud URL *or* http://qdrant:6333 for sidecar)
```

ARM note: `python:3.11-slim` and `qdrant/qdrant` both ship linux/arm64
images; onnxruntime publishes manylinux_aarch64 wheels, so `pip install -r
requirements.txt` resolves natively — no Rosetta/QEMU needed.

## 2. Qdrant: Cloud (default) or sidecar

- **Cloud (recommended start):** keep `QDRANT_URL=https://<cluster>.cloud.io`
  + `QDRANT_API_KEY` in `.env`. The compose sidecar idles unused; the
  278-item collection (~0.6 MB) uses ~0.1% of the free 1 GB. Re-activate the
  cluster in the Cloud dashboard if it suspended after idle weeks.
- **Sidecar:** set `QDRANT_URL=http://qdrant:6333`, blank `QDRANT_API_KEY`,
  then re-ingest once (alias-swap, zero downtime):
  ```bash
  docker compose -f docker-compose.prod.yml up -d qdrant
  python scripts/ingestion/vectorize_corpus.py   # writes under same alias
  ```
  Vectors must match the baked `bge-small-en-v1.5` query model — the stock
  pipeline already does (`passage_embed` at ingest, `query_embed` at serve).

## 3. Build + launch

```bash
docker compose -f docker-compose.prod.yml build api   # bakes ONNX weights (~237 MB)
docker compose -f docker-compose.prod.yml up -d
curl -s http://localhost:8000/health                  # {"status":"ok",...}
```

Edit `Caddyfile` (`api.example.com` → your domain), then Caddy issues TLS
automatically on first request. Set the frontend env
`VITE_API_URL=https://api.<yourdomain>` in Vercel and add it to
`ALLOWED_ORIGINS` in `.env`, then `docker compose -f
docker-compose.prod.yml up -d api` to pick it up.

## 4. Smoke test (live, costs fractions of a cent)

```bash
curl -N "https://api.<yourdomain>/v1/roadmap/stream?goal=Learn%20Python&level=beginner"
# expect: event: structure (<5 s) → 6-10x event: resources → event: done
```

Plus the repo suite any time: `pytest tests/ -q` (mocked, 99 tests, no live
services) and `scripts/prewarm_cache.py` for popular goals so repeat
visitors get sub-second cache hits with zero LLM cost.

## 5. $0 budget check

OCI Always Free (no expiry) + Qdrant Cloud free + Vercel hobby + nano at
$0.10/$0.40 per 1 M tokens (~1–2 k tokens per plan call). Outbound bandwidth
at this traffic sits inside free limits. Total: $0/mo.

## 6. Optional later (not needed day one)

- Restore `bge-base-en-v1.5` (768 d) + re-ingest for a quality upgrade;
  12 GB absorbs it easily.
- Nightly `run_evaluation.py` via systemd timer → seeded `/evaluation`.
- Uptime Kuma/Healthchecks on `/health` (no keep-warm pinging needed —
  nothing sleeps here, unlike Render free).
