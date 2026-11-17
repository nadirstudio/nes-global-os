# NES GLOBAL OS

Corporate operating system for **NADIR E-SKILLS (SMC-PRIVATE) LIMITED** — one command centre, one database, one workforce
(human + AI), one CRM, one project system, one Executive Assistant.

```
backend/    FastAPI + SQLAlchemy + Alembic (API, worker, AI runtime, tests)
frontend/   Next.js 16 static UI (Command Centre and all modules)
deploy/     Docker Compose stack, Caddy, install / backup / restore scripts
docs/       Architecture, company structure, schema, agent registry, permissions, status, guides
```

Start here: `docs/PROJECT_STATUS.md` → `docs/DEPLOYMENT_GUIDE.md` (`deploy/install.sh` on Ubuntu Server 24.04).

Milestone 1 verified: 26 backend tests on PostgreSQL 16, frontend build + headless browser check, encrypted backup/restore.
