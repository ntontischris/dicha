# Deployment — Hetzner (Docker + Caddy, free HTTPS)

This service is a single FastAPI app (`start.py → uvicorn webhook:app`). The WordPress
plugin in **each** WooCommerce shop syncs data to `POST /webhook`, and the chat widget
calls `POST /chat`. **All shops point to ONE instance** of this service (multi-tenant —
each shop is separated by its own `Project ID`).

## ⚠️ Hard rule: ONE process
The app keeps in-memory chat sessions + an in-process thread pool. Run **exactly one
container**. Never set `deploy.replicas > 1` and never add `uvicorn --workers`.
Concurrency is handled internally (`AGENT_WORKERS`, default 12).

## Prerequisites
- A Hetzner VPS (e.g. CPX11 / CX22, Ubuntu 24.04) with Docker + Compose installed.
- A Supabase project already provisioned with the schema **and data** (this deployment
  uses a full `pg_dump` clone of the existing DB — see the migration runbook in
  `docs/superpowers/plans/2026-06-05-client-infra-migration.md`).
- The client's `OPENAI_API_KEY` and `COHERE_API_KEY` (reranking is kept ON).
- A public hostname with HTTPS (free options below).

## Environment variables (`.env`)
Create `.env` from `.env.example`. Full list the app reads:

| Var | Required | Note |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | client's key |
| `SUPABASE_URL` | ✅ | `https://<ref>.supabase.co` |
| `SUPABASE_KEY` | ✅ | **service_role** key — server-side only |
| `WEBHOOK_SECRET` | ⚠️ set it | empty = auth disabled; must match each shop's plugin "API Token" |
| `COHERE_API_KEY` | kept ON | reranking quality |
| `PROJECT_ID` | optional | default tenant; each shop sets its own |
| `EMBEDDING_MODEL` | optional | keep 1536-dim (`text-embedding-3-large`) |
| `CONTEXT_MODEL` | optional | `gpt-4o-mini` |
| `MODEL`, `TOOL_MODEL`, `ANSWER_MODEL` | optional | model defaults |
| `TIER_FAST_TOOL/ANSWER`, `TIER_POWERFUL_TOOL/ANSWER` | optional | Γρήγορο/Δυνατό mapping |
| `AGENT_WORKERS` | optional | thread-pool size (keep one container) |
| `PORT` | optional | `8000` |

## 1. Free public hostname (no domain purchase)
The plugin requires HTTPS with a valid certificate, and Let's Encrypt only issues for
**hostnames, not bare IPs**. Pick one:

- **DuckDNS (recommended):** create a free subdomain at <https://www.duckdns.org> and set
  its IP to your VPS IP → e.g. `dicha-agent.duckdns.org`. Stable: if the VPS IP ever
  changes, update it once on DuckDNS and the shops never need touching.
- **nip.io (instant):** use `<dashed-ip>.nip.io` (e.g. `203-0-113-45.nip.io`). Zero setup,
  but the hostname contains the IP, so an IP change means re-pointing every shop.

## 2. Configure
```bash
cp .env.example .env          # fill in real values
chmod 600 .env
cp Caddyfile.example Caddyfile # replace the hostname with your DuckDNS/nip.io host
sudo ufw allow 80 && sudo ufw allow 443
```
Make sure the hostname resolves to the VPS **before** the first start (Caddy needs it to
issue the certificate).

## 3. Run
```bash
docker compose up -d --build
docker compose ps                  # app should become healthy
docker compose logs app | tail     # expect "Webhook service started (agent workers=12)" ONCE
```

## 4. Verify
```bash
curl -fsS https://<your-host>/health     # -> {"status":"ok",...} with valid TLS
```

## 5. Point each shop's plugin (no code change)
In every shop's WP admin → **Settings → Agency Sync Agent**:
- **API Endpoint:** `https://<your-host>/webhook` (the `/webhook` suffix is **mandatory**)
- **API Token:** the same value as `WEBHOOK_SECRET`
- **Project ID:** a **unique** id per shop
Then **Save → Test Connection → Run Sync Now**.

The plugin itself lives in this repo under [`wp-plugin/`](wp-plugin/):
- `wp-plugin/dicha-sync-v3.zip` — ready to install (WP admin → Plugins → Add New → Upload Plugin)
- `wp-plugin/dicha-sync-v3/` — plugin source
- After editing the source, rebuild the zip with `python wp-plugin/make_zip.py`

## Operations
- Auto-restart on crash/reboot: `restart: unless-stopped` (already set).
- Logs: `docker compose logs -f app`.
- Update: `git pull && docker compose up -d --build`.
- Backups: schedule a daily `pg_dump` of the Supabase DB — company docs, plugin manuals and
  chat logs are **not** reproducible from WooCommerce.
