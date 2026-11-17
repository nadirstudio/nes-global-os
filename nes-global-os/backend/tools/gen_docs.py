"""Regenerates docs that must mirror the code: agent registry, permissions matrix, database schema.
Run:  python tools/gen_docs.py ../docs   (uses NES_DATABASE_URL for the agent registry)"""
import sys
from collections import defaultdict
from sqlalchemy import select
sys.path.insert(0, ".")
from app import models as m
from app.db import Base, SessionLocal
from app.permissions import (AGENT_AUTOMATIC, AGENT_NEEDS_APPROVAL, AGENT_PROHIBITED, MATRIX, ROLES, ROLE_LABELS)
from app.seed import COMPANIES, DEPARTMENTS

out = sys.argv[1]

# ---------------- permissions
L = ["# Permissions Matrix", "", "_Generated from `backend/app/permissions.py` — the code is the source of truth._", "",
     "## Human roles", "", "| Action | " + " | ".join(ROLE_LABELS[r] for r in ROLES) + " |", "|---|" + "---|" * len(ROLES)]
for act, roles in MATRIX.items():
    L.append(f"| `{act}` | " + " | ".join("✅" if r in roles else "—" for r in ROLES) + " |")
L += ["", "## Data scope (multi-company isolation)", "",
      "| Role | Sees |", "|---|---|",
      "| CEO | Everything, all companies |",
      "| Director | Own company + companies explicitly granted (user_company_access) |",
      "| Department Head / Manager | Own department(s) inside their company (and departments they head) |",
      "| Employee / Intern / Freelancer | Only their own tasks, leads they own, projects they are members of |",
      "", "Scope is enforced server-side on every query (`deps.ensure_company / ensure_department`, `Scope`), never in the UI.",
      "Interns and supervised beginners: marking a reviewed task *done* routes it to *review* for the reviewer.",
      "", "## AI agent actions", "", "| Action | Policy | Meaning |", "|---|---|---|"]
for k, v in AGENT_AUTOMATIC.items(): L.append(f"| `{k}` | automatic (if granted) | {v} |")
for k, v in AGENT_NEEDS_APPROVAL.items(): L.append(f"| `{k}` | **human approval** | {v} |")
for k, v in AGENT_PROHIBITED.items(): L.append(f"| `{k}` | **never grantable** | {v} |")
L += ["", "Agents request actions by emitting `ACTION_REQUEST` lines; the runtime checks them against the agent's granted",
      "permissions. Approval-required actions create an Approval record; prohibited or ungranted actions are denied and audited."]
open(f"{out}/PERMISSIONS_MATRIX.md", "w").write("\n".join(L) + "\n")

# ---------------- schema
L = ["# Database Schema", "", "_Generated from `backend/app/models.py`. Migrations: `backend/alembic/versions/`._", "",
     "PostgreSQL 16 is the single system of record. All primary keys are UUIDs so records created on the local office",
     "server and in the cloud can be merged without collisions. Google Sheets is never a primary store.", ""]
for t in Base.metadata.sorted_tables:
    L += [f"## `{t.name}`", "", "| Column | Type | Null | Notes |", "|---|---|---|---|"]
    for c in t.columns:
        notes = []
        if c.primary_key: notes.append("PK")
        for fkey in c.foreign_keys: notes.append(f"→ {fkey.target_fullname}")
        if c.unique: notes.append("unique")
        L.append(f"| {c.name} | {c.type} | {'yes' if c.nullable else 'no'} | {', '.join(notes)} |")
    for con in t.constraints:
        if con.__class__.__name__ == "UniqueConstraint" and len(con.columns) > 1:
            L.append(f"\nUnique together: ({', '.join(c.name for c in con.columns)})")
    L.append("")
open(f"{out}/DATABASE_SCHEMA.md", "w").write("\n".join(L))

# ---------------- agent registry
with SessionLocal() as db:
    comps = {c.id: c for c in db.scalars(select(m.Company))}
    depts = {d.id: d for d in db.scalars(select(m.Department))}
    agents = list(db.scalars(select(m.Agent).where(m.Agent.status != "archived").order_by(m.Agent.code)))
by = defaultdict(lambda: defaultdict(list))
for a in agents:
    by[comps[a.company_id].name][depts[a.department_id].name if a.department_id else "—"].append(a)
L = ["# AI Agent Registry", "", f"_Generated from the database: {len(agents)} agents ({sum(a.is_coordinator for a in agents)} department coordinators)._", "",
     "Every agent ships as **configured** (not active). To go live: add an API key → TEST (real model call) → ACTIVATE.",
     "Model tiers: `claude-opus-5-5` (advanced reasoning: CEO assistant, strategists, dev, legal), `claude-sonnet-5-5`",
     "(research / standard work), `claude-haiku-5-5` (high-volume, cost-efficient: support, classification, reminders).",
     "Opus/Sonnet agents fall back one tier down if their model is unavailable.", ""]
for cname in sorted(by, key=lambda n: (n != "NADIR E-SKILLS (SMC-PRIVATE) LIMITED", n)):
    L += [f"## {cname}", ""]
    for dname, items in sorted(by[cname].items()):
        L += [f"### {dname}", "", "| Agent | Code | Model | Permissions | Responsibilities |", "|---|---|---|---|---|"]
        for a in sorted(items, key=lambda a: (not a.is_coordinator, a.name)):
            L.append(f"| {'◆ ' if a.is_coordinator else ''}{a.name} | `{a.code}` | {a.model} | {', '.join(a.permissions)} | {'; '.join(a.responsibilities)} |")
        L.append("")
open(f"{out}/AI_AGENT_REGISTRY.md", "w").write("\n".join(L))
print("generated", len(agents), "agents")
