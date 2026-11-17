# Deployment Guide

## A. Prepare the server (once)

1. Hardware per SYSTEM_ARCHITECTURE.md §6 — on a **UPS**, wired to the office router.
2. Install **Ubuntu Server 24.04 LTS** from a USB stick (enable OpenSSH during install). Your Windows PCs are not touched.
3. In the router, give the server a fixed LAN IP (DHCP reservation), e.g. `192.168.1.50`.
4. Copy this project to the server (USB, `scp`, or `git clone`), e.g. into `/opt/nes-global-os`.

## B. Install

```bash
cd /opt/nes-global-os/deploy
./install.sh
```

The script installs Docker from Docker's official repository, enables the ufw firewall (SSH/80/443 only), generates
`deploy/.env` with random secrets (`POSTGRES_PASSWORD`, `NES_JWT_SECRET`, `NES_MASTER_KEY`), builds and starts the stack,
runs migrations, seeds the company structure and agent registry, asks for the **CEO login email** and a password (typed
privately — never put passwords on the command line), and installs a nightly encrypted backup at 02:30 PKT.

**Save these two files offline (USB in a safe):** `deploy/.env` and `~/.nesos-backup-key`. Without them stored API keys
and backups cannot be decrypted.

Open `http://<server-ip>/` from any device on the office network.

## C. First sign-in checklist

1. Settings → My security → **enable MFA**.
2. Settings → AI & costs → add your **Anthropic API key** → Test with `claude-haiku-5-5`.
3. Enter **model prices** (USD per million tokens, from your Anthropic console/pricing page) and **monthly/daily budgets**.
4. AI Agent Factory → open *Executive Assistant* → Test → Activate. Then activate other agents as needed.
5. Workforce → add people → create logins. Organisation → set department heads.

## D. Remote access & HTTPS

Pick one:
- **Tailscale (simplest, private):** install Tailscale on the server and on staff devices; use the server's Tailscale name.
  Enable HTTPS certificates in Tailscale and set `NES_COOKIE_SECURE=true`.
- **Public domain with Caddy auto-HTTPS:** point e.g. `os.nadireskills.com` (A record) to your public IP, forward ports
  80/443 to the server, set `NES_SITE_ADDRESS=os.nadireskills.com` and `NES_COOKIE_SECURE=true` in `.env`, then
  `docker compose up -d`.
- **Cloudflare Tunnel:** no port forwarding; run `cloudflared` on the server pointing at `http://localhost:80`.

Keep MFA mandatory for anyone with remote access.

## E. Updating to a new release

```bash
# copy the new zip to the server first (scp from your laptop), then:
unzip -o -j ~/nes-global-os-v1.1.zip 'nes-global-os/deploy/update.sh' -d /opt/nes-global-os/deploy/
cd /opt/nes-global-os/deploy && ./update.sh ~/nes-global-os-v1.1.zip
```
`update.sh` takes a backup, copies the new version (keeping `deploy/.env`), rebuilds, runs migrations and the seed.

## E2. Operations

```bash
cd /opt/nes-global-os/deploy
docker compose ps                      # status
docker compose logs -f api worker      # logs
docker compose pull && docker compose up -d --build   # upgrade after updating the code
docker compose exec api python -m app.cli seed        # re-run seed (adds missing items only)
./backup.sh                            # manual backup
```

Migrations run automatically when the `api` container starts (`alembic upgrade head`).

## F. Development (for Claude Code / developers)

```bash
# backend
cd backend && pip install -r requirements-dev.txt
export NES_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/nesos
alembic upgrade head && python -m app.cli seed && python -m app.cli create-ceo --email you@example.com
uvicorn app.main:app --reload            # API docs at /api/docs
python -m app.worker                     # scheduler
pytest -q                                # uses NES_TEST_DATABASE_URL (default …/nesos_test) — it is wiped
# frontend
cd frontend && npm ci && npm run dev     # http://localhost:3000, proxies /api to :8000
python backend/tools/gen_docs.py docs    # regenerate registry/permissions/schema docs
```
