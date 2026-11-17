# Project Status

Last verified milestone: **Milestone 2.1 — free calls in NES Team** · 17 Nov 2026
(Milestone 1 — working core, 9 Nov 2026; installed on the office server 12 Nov 2026.)

Legend: ✅ built and tested · 🟡 built, needs your credentials/hardware to go live · 📐 designed, not built · ⏳ not started

| Phase | Scope | Status | Evidence |
|---|---|---|---|
| 1 | Business audit & architecture | ✅ | COMPANY_STRUCTURE.md, SYSTEM_ARCHITECTURE.md |
| 2 | Local & cloud infrastructure | ✅ local stack · 📐 cloud/sync | docker-compose.yml, Caddyfile, install.sh (compose validated; images **not built in the dev sandbox — no Docker daemon there**) |
| 3 | Core backend & PostgreSQL | ✅ | 25 tables, Alembic migration 0001, tested on PostgreSQL 16 |
| 4 | Authentication & users | ✅ | bcrypt, lockout, MFA (TOTP), rate limits, roles, scoping — tests pass |
| 5 | CEO Global Command Centre | ✅ | All 17 requested panels from live data; verified in headless Chrome, desktop + mobile |
| 6 | Human workforce | ✅ | Profiles, categories, skill levels, logins, onboarding tasks, attendance |
| 7 | AI Agent Factory | ✅ | Full lifecycle, live-test gate, budgets, fallback, history, costs |
| 8 | CEO Executive Assistant | ✅ data answers · 🟡 AI narrative | Works data-only now; Claude narrative once an API key is added and the agent is tested + activated |
| 9 | Department AI workforce | 🟡 | 114 agents seeded (23 coordinators) as *configured*; activate per agent after a passing test |
| 10 | CRM & project management | ✅ | 8 pipelines, dedupe, scoring, history, won→customer; projects, milestones, budgets |
| 11 | Google Workspace | ⏳ | Needs OAuth client (see INTEGRATION_STATUS.md) |
| 12 | WhatsApp Cloud API | ⏳ | Needs Meta WABA + number IDs |
| 13 | Finance & HR | ✅ finance core · ⏳ payroll | Entries, multi-currency, invoices, receipts, profitability. Payroll: migrate the existing Apps Script app |
| 14 | Business intelligence | ✅ core | Snapshot, alerts, workforce engine, department health, reports |
| 15 | Testing, security, deployment | ✅ core | 26 backend tests on PostgreSQL; encrypted backup/restore verified; security headers |
| 16 | Bootable NES Linux | 📐 | Roadmap in SYSTEM_ARCHITECTURE.md §8 |
| M2 | **NES Team Android app — release 1** | ✅ API + app tested · 🟡 APK build on GitHub | Geofence + biometric check-in, leave/overtime/shifts, tasks, approvals, chat, news, directory, documents, AI help desk, device wipe. 34 backend tests; full employee + manager flow run in a phone-sized browser. APK compiles on GitHub Actions (not verifiable in the dev sandbox). See EMPLOYEE_APP.md |
| M2.1 | **Free voice & video calls** | ✅ tested · 🟡 APK on GitHub | WebSocket signalling (Redis across workers), WebRTC phone-to-phone, 1:1 voice/video, group voice ≤6, missed calls, presence, office-address failover so calls work on Wi-Fi without internet. 38 backend tests; real calls verified between 3 browser phones |
| M3 | Employee app — release 2 | ⏳ | Payroll in NES OS + payslips/tax/loans, expense claims with receipt photos, offline mode, polls & kudos |
| M4 | Employee app — release 3 | ⏳ | Ringing on a closed app (native service), earpiece switch, bigger group calls (LiveKit), Google SSO, background push, device posture checks |

## Known limitations (honest list)

- The Android APK has not yet been compiled — Google's Android SDK can't be downloaded in the dev sandbox. It builds on
  GitHub Actions; the first run may need a small fix.
- Employee-app notifications only arrive while the app is open/recent (30 s polling); background push comes in release 3.

- Docker images were not built in the development sandbox (no Docker daemon). First real build happens on your server via
  `install.sh`; report any build error and it will be fixed.
- Agents generate text output (drafts, analyses, reports). Tools that touch the outside world (Gmail drafts, WhatsApp
  replies, web research, Drive) arrive with the Phase 11–12 connectors. Their tool names exist but are inert until then.
- Approvals record the human decision; actual sending happens once the matching integration exists.
- Payroll, salary documents and PDFs from the existing Apps Script finance app are not yet migrated.
- Employee Hub documents are stored on the server (Docker volume, included in backups); cloud object storage is Phase 2.
- Browser storage of the session is a cookie; on plain-HTTP LAN installs set up HTTPS (domain or Tailscale) before remote use.

## Next milestone (recommended order)

1. Install on the server; add Anthropic API key; set model prices + budgets; test & activate the Executive Assistant and
   2–3 high-value agents (e.g. Consultancy Lead Qualification, DM Proposal Agent).
2. Phase 11: Google OAuth → Gmail inquiry → lead creation; Calendar for appointments; Sheets exports.
3. Phase 12: WhatsApp Cloud API shared inbox.
4. Phase 2: remote access (Tailscale/Cloudflare Tunnel) and off-site backups; then cloud primary + outbox sync.
5. Migrate Accounting & Payroll and Embassy Appointment Apps Script apps into PostgreSQL modules.
