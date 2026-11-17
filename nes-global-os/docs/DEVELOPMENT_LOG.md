# Development Log

## 2026-11-09 — Milestone 1: working core

**Inputs:** master specification v1.0. No screenshot or project source files were attached in this session, so the
Command Centre follows the written visual direction (dark charcoal/navy, electric blue + cyan, green/amber/red states).
If you share the reference screenshot, the dashboard will be aligned to it.

**Audit:** fetched nadireskills.com, consultant.nadireskills.com, academy.nadireskills.com, nesdigitalmarketing.com →
COMPANY_STRUCTURE.md (services, journeys, contacts, discrepancies).

**Built**
- Backend: FastAPI app, 25-table PostgreSQL schema (UUID keys), Alembic migration `0001`.
- Auth: bcrypt, lockout (5 fails / 15 min), Redis rate limits, TOTP MFA, httpOnly cookie, token versioning.
- RBAC matrix (7 roles) + server-side company/department/own-work scoping; audit log on every write.
- Organisation: companies, departments, live org tree.
- Workforce: 15 employment categories, 5 skill levels, logins, onboarding tasks by level, attendance (check-in/late rule 09:15 PKT).
- AI: provider abstraction (Anthropic, OpenAI, Gemini, OpenAI-compatible) over official HTTP APIs; encrypted keys;
  live tests; fallback chain; token + cost tracking from admin-entered prices; group/agent budgets; honest status.
- Agent Factory: lifecycle create/configure/test/activate/pause/restart/update/duplicate/archive; duplicate-name guard;
  prohibited permissions rejected; action-request governance → approvals.
- Tasks, approvals, workforce intelligence (utilisation, quality, on-time, CSAT, flags, skill-aware recommendations).
- CRM: per-company pipelines, phone normalisation (+92), duplicate protection, rule-based scoring, history, won→customer.
- Projects (milestones, budget use, revenue), finance (multi-currency entries, invoices, receipts, profitability, top services).
- Intelligence snapshot, alerts, department health; Executive Assistant (data-grounded + optional Claude narrative).
- Reports: daily briefing, recommendations, progress, close, weekly, monthly; worker schedule (Mon–Sat, PKT) with once-only claims.
- Frontend: Next.js 16 static export, 11 screens, PWA manifest, responsive.
- Deployment: Dockerfiles, Compose, Caddy (CSP/HSTS), install.sh (Docker, ufw, secrets, seed, CEO, backup cron),
  encrypted backup/restore with rotation and rclone.
- Seed: 8 companies, 24 departments, 8 pipelines, 114 agents (23 coordinators), 13 integrations — idempotent.

**Verified**
- `pytest`: 26 tests pass against PostgreSQL 16 (auth, lockout, MFA, isolation, own-task rules, supervised review,
  agent lifecycle, quota/auth/fallback, key secrecy, cost & budget block, governance + injection wrapping,
  assistant with/without AI, CRM, finance, workforce, onboarding, attendance, projects/dashboard, integrations, worker schedule).
- Frontend: `tsc` clean; `next build` OK; all screens rendered in headless Chrome with 0 console errors; mobile layout checked.
- Backup → restore round trip into a fresh database (checksums verified).
- `docker compose config` valid.

**Not verified here:** Docker image builds and Caddy runtime (no Docker daemon in the sandbox).

**Fixes during the session:** circular FK departments↔people (`use_alter`), SQLAlchemy 2.1 positional GROUP BY,
ambiguous joins in reports, invoice `issued_on` double-set, group reports restricted to CEO, Next.js upgraded from a
version with a published security advisory to 16.4.5.

## 2026-11-12 — First real install on the office server
- `install.sh` ran on Ubuntu Server 24.04 (nes-server, 192.168.1.27): Docker build, migrations, seed (8/24/114/8/13) and CEO account all succeeded.
- Bug found: the backup-cron line aborted the script under `set -euo pipefail` when no crontab existed (empty `grep -v`), so the nightly backup was not installed and the final message didn't print. Fixed in install.sh; existing server fixed by hand.

## 2026-11-17 — Milestone 2: NES Team employee app (release 1)

Decisions (CEO): Tailscale for access, APK built on GitHub, HR & work features first, payroll to be built into NES OS.

**Backend:** migration `0002` (11 tables + attendance evidence columns, safe for existing rows; upgrade/downgrade verified),
`/api/mobile/*` (device-bound login, home, sync, geofenced check-in/out, leave & overtime with balances and approvals,
field check-in review, shifts, directory, news, chat with Fernet-encrypted messages, documents with 5-minute file links,
AI help desk restricted to the employee's own data + published policies) and `/api/hub/*` (work sites, devices with
remote sign-out + wipe, leave/attendance policies, document upload with type/magic-byte checks, 20 MB limit and text
extraction from PDF/DOCX). Web check-in is disabled for staff once office locations exist. New *Employee Help Desk*
agent; new agents inherit the provider/model the company uses (e.g. Groq). CORS limited to the app origin, no credentials.

**Mobile:** `mobile/` — Capacitor 8 + React 19, 15 screens, biometric app lock (2-min background timeout), GPS,
notifications, back button, NES icons/splash. Android: FLAG_SECURE, no backup, permissions, release signing from
secrets. `.github/workflows/nes-team-apk.yml` builds and signs the APK. Release signing key generated and delivered
separately.

**Portal:** new *Employee Hub* page (leave & field check-ins, office locations, announcements, documents, shifts, phones, HR rules).

**Ops:** `deploy/update.sh` (backup → copy new version keeping `.env` → rebuild → migrate → seed); backups now include
uploaded documents; `files_data` volume.

**Verified:** 34 backend tests on PostgreSQL 16 (8 new); mobile `tsc` + `vite build`; 21-step employee + manager flow in
headless Chrome at phone size against the live API (CORS, GPS, simulated fingerprint): check-in inside the geofence,
leave request, manager approval on a second phone, balances, chat both ways, documents, help desk; every Employee Hub tab
rendered with 0 console errors. Bugs found and fixed during testing: check-in sheet flipping to "Check out" after
success, scroll position carried between screens, bottom menu covering the Ask HR input, help desk citing a document
for a data-only answer, duplicate device entries on re-login.

**Not verified here:** Gradle/APK build (no Android SDK in sandbox), Docker image rebuild, file-volume backup.

## 2026-11-17 — Milestone 2.1: free calls (CEO moved calling ahead of payroll; 25–50 staff)

**Backend:** migration `0003` (calls, call_participants). `app/realtime.py` — WebSocket hub with Redis pub/sub so
messages reach a user on any of the API worker processes, plus presence. `app/routers/calls.py` — 60-second
WebSocket tickets (no long-lived token in URLs/logs), call state machine (ringing → active → ended / missed /
declined / cancelled), ring timeout, relay of WebRTC offer/answer/ICE only between participants of the same live call,
group calls from chat channels (membership checked, cap 6, video → voice above 4), history, unseen missed calls,
stale-call cleanup at start-up. Directory shows who's online; home/sync include missed calls.

**App:** `calls.ts` (WebSocket with reconnect + ping, WebRTC mesh, ringtone/ringback via Web Audio, notification when
the app is in the background), call screens (incoming / outgoing / in-call video grid with self view / ended),
free-call buttons in People, contact card, chat header (direct = 1:1, groups = group call) and call history.
Office-address failover in the API client (office Wi-Fi first, Tailscale otherwise). Android: microphone, camera,
vibrate permissions.

**Verified:** 38 backend tests (4 new: tickets, direct call answer/relay/hang-up/history, decline/missed/cancel,
group call + channel permission). Real WebRTC in headless Chrome with fake camera/mic, API on **2 workers**:
1:1 video with 640×480 video and audio both ways, mute, hang-up, decline, 3-person group voice call with live audio
from both others, one person leaving, call ending, call history. 0 console errors.

**Not verified here:** audio routing and ringing behaviour on real Android phones (needs the APK).
