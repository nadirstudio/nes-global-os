# NES GLOBAL OS — System Architecture

Version 1.0 · Milestone 1 (core) · 9 Nov 2026

## 1. What it is

A browser-based corporate operating system for NADIR E-SKILLS (SMC-PRIVATE) LIMITED and its business units, running on a
dedicated Linux server in the office and reachable from Windows, macOS, Linux, Android and iOS through any modern browser.
It is installable as a PWA (Add to Home Screen / Install app). No client software is required.

## 2. Components (built and tested in Milestone 1)

```
 Browsers / PWA (any OS)                          AI providers (HTTPS, server-side only)
        │  HTTPS (Caddy, auto-TLS)                 Anthropic Claude · OpenAI · Gemini · OpenAI-compatible
        ▼                                                        ▲
 ┌──────────────── Caddy (web) ────────────────┐                 │
 │ static Next.js UI  ·  /api/* → FastAPI      │                 │
 └─────────────────────┬───────────────────────┘                 │
                       ▼                                         │
 ┌─────────── FastAPI (api) ───────────┐   ┌──── worker ─────────┴───────┐
 │ auth+MFA · RBAC+scoping · audit     │   │ daily ops schedule (PKT)    │
 │ org · workforce · agents · tasks    │   │ reports · agent task queue  │
 │ CRM · projects · finance · AI usage │   │ once-only job claims        │
 │ dashboard · Executive Assistant     │   └──────────────┬──────────────┘
 └──────────┬───────────────┬──────────┘                  │
            ▼               ▼                             │
     PostgreSQL 16     Redis 7 (rate limits, cache) ◄─────┘
   (system of record)
```

| Layer | Technology | Why |
|---|---|---|
| UI | Next.js 16 (React 19, TypeScript), static export | Fast, works on LAN without internet, no Node server to run |
| API | Python 3.13, FastAPI, SQLAlchemy 2.1, Alembic | Typed, testable, good AI ecosystem |
| Database | PostgreSQL 16 | Single system of record; UUID keys for safe local↔cloud merge |
| Queue / cache | Redis 7 | Rate limiting now; job queue headroom later |
| Background | `app.worker` (same codebase) | Scheduled operations + agent queue, idempotent via `job_runs` |
| Proxy | Caddy 2 | Automatic HTTPS, security headers, static files |
| Packaging | Docker Compose on Ubuntu Server 24.04 LTS | One-command install, upgrades, restarts |

## 3. Key design decisions (improvements over the brief)

1. **Facts first, AI second.** `intelligence.snapshot()` computes every metric from PostgreSQL. The dashboard, reports and
   Executive Assistant all use it. Claude only writes prose *over* those verified facts. If no provider is connected, the
   system still answers with data-only results and says why the AI narrative is missing. This is what guarantees "no fake
   statistics".
2. **Agents can't be "active" without proof.** Lifecycle: draft → configured → test (a real model call) → active. Changing
   an agent's instructions, model, tools or permissions sends it back for a fresh test. Operational status is computed live
   from provider health, budgets and lifecycle — never stored as a flag that could lie.
3. **Agents never act directly.** They return text plus optional `ACTION_REQUEST` lines. The runtime checks each request
   against the agent's grants: automatic actions are logged, approval actions create an Approval, prohibited actions
   (payments, deletions, bank details, legal commitments, disclosure) are denied and can never be granted.
4. **Prompt-injection containment.** Customer/email/document text is wrapped in `<untrusted_data>` (closing tags stripped),
   the system prompt forbids following instructions inside it, and — more importantly — even a manipulated model output
   cannot do anything beyond the permission gate in (3).
5. **Company isolation is server-side.** Every query is filtered by the caller's `Scope` (companies / departments / own work).
   Group-wide reports are CEO-only because they span all companies.
6. **UUID primary keys everywhere** so the planned local+cloud topology can merge data without ID collisions.
7. **Workforce intelligence is quality-aware.** Utilisation uses estimated hours vs. capacity; performance uses on-time rate,
   reviewer quality scores and customer satisfaction — not task counts. Recommendations only match *real* unassigned tasks
   (no busywork), respect skill level (beginners get basic work with a reviewer), and are applied only after a department
   head accepts them.

## 4. Claude: subscription vs. API (important)

| Thing | What it's for in NES GLOBAL OS |
|---|---|
| **Claude.ai subscription** (what you bought) | You (and Claude) designing, building and maintaining this codebase. It does **not** power background agents. |
| **Claude Code** | Coding agent included with eligible paid plans; use it to continue development from this repo. |
| **Anthropic API** (console.anthropic.com) | Separate, pay-per-token account. Needed for agents to run autonomously on the server. |
| **Deployed agent runtime** | `backend/app/ai/runtime.py` — calls the API with your key, tracks tokens and cost, enforces budgets. |

The system never assumes unlimited API access: group monthly/daily budgets, per-agent monthly budgets and daily token caps
block calls once reached, and the dashboard shows the real reason (BUDGET LIMIT, QUOTA EXHAUSTED, AUTHENTICATION REQUIRED…).
Prices per model are entered by the administrator, so cost figures always match your actual contract.

## 5. Hybrid local + cloud design

**Milestone 1 (built):** everything runs on the office server. Remote staff connect securely through Tailscale or a
Cloudflare Tunnel (no router port-forwarding, no public database). Nightly encrypted backups can be copied off-site with
`rclone` (Google Drive, S3, Backblaze B2). This is the most reliable starting point for an office with load-shedding risk.

**Phase 2 (designed, not yet built):**

- Cloud VPS runs the primary PostgreSQL + a public API/UI instance (`NES_SITE_ROLE=cloud`).
- The office server runs the same containers with `NES_SITE_ROLE=local`, a streaming read replica for fast LAN reads, the
  worker, file processing and integration gateways.
- **Offline writes** go to a local `outbox` table as *commands* (e.g. "check-in person X", "move lead Y to stage Z") with a
  UUID idempotency key and the record version they were based on. When connectivity returns, the outbox replays to the cloud
  in order. A command whose base version is stale is **not** silently applied; it is parked in a conflict queue for a human.
  Result: no uncontrolled conflicts and no duplicate records.
- The UI shows sync state (`cloud_sync` integration: CONNECTED / ERROR / PAUSED, queued-command count).
- **Google Sheets** is export-only from PostgreSQL (reports and approved trackers). Imports from Sheets go through a
  validation preview and duplicate check before anything is written.

## 6. Hardware & hosting requirements

**Office server (Milestone 1, all services local):**

| | Minimum | Recommended |
|---|---|---|
| CPU | 4 cores (Intel i5 8th gen / Ryzen 3) | 6–8 cores |
| RAM | 16 GB | 32 GB |
| Storage | 512 GB NVMe SSD | 1 TB NVMe + separate disk/NAS for local backups |
| Network | Wired gigabit Ethernet, static LAN IP (DHCP reservation) | + second internet line or 4G failover |
| Power | **UPS (≥1 kVA, 30+ min)** — essential with load-shedding | UPS with USB shutdown signal |
| OS | Ubuntu Server 24.04 LTS (Windows PCs are untouched) | same |

AI models run in the provider's cloud, so no GPU is needed. Local LLMs are a possible later addition (needs a GPU with
≥16 GB VRAM) and are not planned for Phase 1.

**Cloud (Phase 2):** a 2 vCPU / 4 GB VPS (or a managed PostgreSQL) in a nearby region (e.g. Middle East / Mumbai / Singapore),
plus object storage for documents and off-site backups.

## 7. Security summary

bcrypt passwords (strength rules) · account lockout after 5 failures · per-IP login and API rate limits (Redis) · TOTP MFA ·
httpOnly SameSite=Strict session cookie (no tokens in JS) · token versioning (log out everywhere, role change revokes) ·
Fernet-encrypted secrets at rest (`NES_MASTER_KEY`) · keys never returned to the browser (only last-4 hint) · CSP and
security headers at Caddy · DB/Redis not exposed outside Docker network · full audit log of every write, login, agent run
and decision · ufw firewall (22/80/443 only).

## 8. Roadmap to a bootable NES Linux (Phase 16)

1. Ubuntu Server **autoinstall** ISO (`cloud-init` autoinstall YAML) that installs Docker and NES GLOBAL OS unattended.
2. NES branding: Plymouth boot splash, GRUB theme, login banner.
3. Optional kiosk mode for the reception/CEO screen: `cage` (Wayland kiosk) launching Chromium on the Command Centre.
4. Built with `live-build` or Cubic; signed checksums; A/B upgrade via container images, not the ISO.
Existing Windows machines are never replaced — they keep using the browser/PWA.
