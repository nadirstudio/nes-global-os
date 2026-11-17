"""AI Agent Factory and lifecycle management."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from .. import models as m
from ..ai.providers import PROVIDERS
from ..ai.runtime import operational_status, run_agent
from ..deps import Ctx, ensure_department, require
from ..permissions import AGENT_AUTOMATIC, AGENT_NEEDS_APPROVAL, AGENT_PROHIBITED, sanitize_agent_permissions
from ..util import apply, get_or_404, row

router = APIRouter(prefix="/agents", tags=["ai-agents"])

TOOLS = {
    "crm_read": "Read CRM leads/customers of own company",
    "crm_write": "Update CRM notes, scores and stage suggestions",
    "tasks_read": "Read tasks of own department",
    "reports_read": "Read generated reports",
    "web_research": "Web research (requires a configured search integration)",
    "gmail_draft": "Create Gmail drafts (requires Google integration)",
    "whatsapp_draft": "Prepare WhatsApp replies (requires WhatsApp integration)",
    "drive_read": "Read approved Google Drive folders (requires Google integration)",
}
MODEL_SUGGESTIONS = {
    "anthropic": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
    "openai": [], "gemini": [], "openai_compatible": [],
}


class AgentIn(BaseModel):
    name: str
    company_id: uuid.UUID
    department_id: uuid.UUID | None = None
    designation: str | None = None
    job_description: str | None = None
    responsibilities: list[str] = []
    instructions: str | None = None
    knowledge: str | None = None
    provider: str = "anthropic"
    model: str = "claude-sonnet-5-5"
    fallbacks: list[dict] = []
    tools: list[str] = []
    permissions: list[str] = []
    supervisor_person_id: uuid.UUID | None = None
    supervisor_agent_id: uuid.UUID | None = None
    is_coordinator: bool = False
    schedule: list[dict] = []
    monthly_budget: Decimal | None = None
    daily_token_limit: int | None = None


class AgentPatch(BaseModel):
    name: str | None = None
    department_id: uuid.UUID | None = None
    designation: str | None = None
    job_description: str | None = None
    responsibilities: list[str] | None = None
    instructions: str | None = None
    knowledge: str | None = None
    provider: str | None = None
    model: str | None = None
    fallbacks: list[dict] | None = None
    tools: list[str] | None = None
    permissions: list[str] | None = None
    supervisor_person_id: uuid.UUID | None = None
    supervisor_agent_id: uuid.UUID | None = None
    is_coordinator: bool | None = None
    schedule: list[dict] | None = None
    monthly_budget: Decimal | None = None
    daily_token_limit: int | None = None


def _clean(data: dict) -> dict:
    if "provider" in data and data["provider"] not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider. Use: {', '.join(PROVIDERS)}")
    if "permissions" in data and data["permissions"] is not None:
        bad = [p for p in data["permissions"] if p in AGENT_PROHIBITED]
        if bad:
            raise HTTPException(400, f"These actions can never be granted to agents: {', '.join(bad)}")
        data["permissions"] = sanitize_agent_permissions(data["permissions"])
    if "tools" in data and data["tools"] is not None:
        data["tools"] = sorted({t for t in data["tools"] if t in TOOLS})
    if data.get("fallbacks"):
        data["fallbacks"] = [{"provider": f["provider"], "model": f["model"]} for f in data["fallbacks"]
                             if f.get("provider") in PROVIDERS and f.get("model")]
    return data


def _code(db, company_id, name) -> str:
    comp = db.get(m.Company, company_id)
    base = f"{comp.code if comp else 'NES'}-{re.sub(r'[^A-Z0-9]+', '-', name.upper()).strip('-')}"[:54]
    code, n = base, 1
    while db.scalar(select(m.Agent).where(m.Agent.code == code)):
        n += 1
        code = f"{base}-{n}"
    return code


def _scope_check(ctx: Ctx, a: m.Agent | AgentIn) -> None:
    if ctx.scope.department_ids is not None:
        ensure_department(ctx, a.company_id, a.department_id)
    else:
        ensure_department(ctx, a.company_id, None)


def _metrics(db, agent_id) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    r = db.execute(select(func.count(), func.count().filter(m.AgentRun.status == "succeeded"),
                          func.count().filter(m.AgentRun.status == "failed"),
                          func.count().filter(m.AgentRun.status == "blocked"),
                          func.coalesce(func.sum(m.AgentRun.input_tokens + m.AgentRun.output_tokens), 0),
                          func.coalesce(func.sum(m.AgentRun.cost), 0))
                   .where(m.AgentRun.agent_id == agent_id, m.AgentRun.started_at >= since)).one()
    tasks_done = db.scalar(select(func.count()).where(m.Task.assignee_agent_id == agent_id, m.Task.status == "done",
                                                      m.Task.completed_at >= since))
    queue = db.scalar(select(func.count()).where(m.Task.assignee_agent_id == agent_id,
                                                 m.Task.status.in_(["todo", "in_progress"])))
    return {"runs_30d": r[0], "succeeded_30d": r[1], "failed_30d": r[2], "blocked_30d": r[3],
            "success_rate": round(100 * r[1] / r[0]) if r[0] else None, "tokens_30d": int(r[4]),
            "cost_30d_usd": float(r[5]), "tasks_done_30d": tasks_done, "queue": queue}


@router.get("/catalog")
def catalog(ctx: Ctx = Depends(require("agents.view"))):
    return {"providers": {k: v["label"] for k, v in PROVIDERS.items()}, "model_suggestions": MODEL_SUGGESTIONS,
            "tools": TOOLS, "automatic": AGENT_AUTOMATIC, "needs_approval": AGENT_NEEDS_APPROVAL,
            "prohibited": AGENT_PROHIBITED,
            "lifecycle": ["draft", "configured", "testing", "active", "paused", "archived"]}


@router.get("")
def list_agents(company_id: uuid.UUID | None = None, include_archived: bool = False,
                ctx: Ctx = Depends(require("agents.view"))):
    q = select(m.Agent).order_by(m.Agent.company_id, m.Agent.is_coordinator.desc(), m.Agent.name)
    if company_id:
        q = q.where(m.Agent.company_id == company_id)
    if not include_archived:
        q = q.where(m.Agent.status != "archived")
    out = []
    for a in ctx.db.scalars(q):
        if not ctx.scope.allows_company(a.company_id):
            continue
        if ctx.scope.department_ids is not None and a.department_id not in ctx.scope.department_ids:
            continue
        out.append(row(a, runtime=operational_status(ctx.db, a)))
    return out


@router.get("/{aid}")
def get_agent(aid: str, ctx: Ctx = Depends(require("agents.view"))):
    a = get_or_404(ctx.db, m.Agent, aid, "Agent")
    _scope_check(ctx, a)
    runs = list(ctx.db.scalars(select(m.AgentRun).where(m.AgentRun.agent_id == a.id)
                               .order_by(m.AgentRun.started_at.desc()).limit(25)))
    queue = list(ctx.db.scalars(select(m.Task).where(m.Task.assignee_agent_id == a.id,
                                                     m.Task.status.in_(["todo", "in_progress", "review"]))
                                .order_by(m.Task.due_at.nulls_last()).limit(25)))
    return row(a, runtime=operational_status(ctx.db, a), metrics=_metrics(ctx.db, a.id),
               runs=[row(r) for r in runs], queue=[row(t) for t in queue])


@router.post("", status_code=201)
def create_agent(body: AgentIn, ctx: Ctx = Depends(require("agents.manage"))):
    _scope_check(ctx, body)
    data = _clean(body.model_dump())
    dup = ctx.db.scalar(select(m.Agent).where(m.Agent.company_id == body.company_id,
                                              m.Agent.department_id == body.department_id,
                                              func.lower(m.Agent.name) == body.name.lower(),
                                              m.Agent.status != "archived"))
    if dup:
        raise HTTPException(409, f"An agent named '{dup.name}' already exists in this department. "
                                 "Update or duplicate it instead of creating a copy.")
    a = m.Agent(**data, code=_code(ctx.db, body.company_id, body.name),
                status="configured" if body.instructions else "draft")
    ctx.db.add(a)
    ctx.db.flush()
    ctx.audit("agent.create", "agent", a.id, a.company_id, name=a.name)
    ctx.db.commit()
    return row(a, runtime=operational_status(ctx.db, a))


@router.patch("/{aid}")
def update_agent(aid: str, body: AgentPatch, ctx: Ctx = Depends(require("agents.manage"))):
    a = get_or_404(ctx.db, m.Agent, aid, "Agent")
    _scope_check(ctx, a)
    if a.status == "archived":
        raise HTTPException(400, "Archived agents cannot be edited. Duplicate it to reuse the configuration.")
    data = _clean(body.model_dump(exclude_unset=True))
    changed = apply(a, data, set(AgentPatch.model_fields))
    if changed:
        a.version += 1
        behaviour = {"instructions", "provider", "model", "permissions", "tools", "knowledge"}
        if behaviour & set(changed) and a.status in {"active", "testing"}:
            # Behaviour changed: require a fresh successful test before it runs autonomously again.
            a.status, a.last_test_ok = "configured", None
        elif a.status == "draft" and a.instructions:
            a.status = "configured"
    ctx.audit("agent.update", "agent", a.id, a.company_id, fields=sorted(changed), version=a.version)
    ctx.db.commit()
    return row(a, runtime=operational_status(ctx.db, a))


class TestIn(BaseModel):
    prompt: str = "Introduce yourself in two sentences and list your three main responsibilities."


@router.post("/{aid}/{action}")
def lifecycle(aid: str, action: str, body: TestIn | None = None, ctx: Ctx = Depends(require("agents.manage"))):
    a = get_or_404(ctx.db, m.Agent, aid, "Agent")
    _scope_check(ctx, a)
    st = a.status
    if action == "configure":
        if not (a.instructions and a.provider and a.model):
            raise HTTPException(400, "Add instructions, provider and model before marking as configured.")
        if st not in {"draft", "configured"}:
            raise HTTPException(400, f"Cannot configure an agent that is {st}")
        a.status = "configured"
    elif action == "test":
        if st == "archived":
            raise HTTPException(400, "Archived agents cannot be tested")
        run = run_agent(ctx.db, a, (body or TestIn()).prompt, "test", actor_user_id=ctx.user.id, max_tokens=400)
        a.last_tested_at, a.last_test_ok = datetime.now(timezone.utc), run.status == "succeeded"
        if st in {"draft", "configured"}:
            a.status = "testing"
        ctx.audit("agent.test", "agent", a.id, a.company_id, ok=a.last_test_ok)
        ctx.db.commit()
        return {"ok": a.last_test_ok, "run": row(run), "agent": row(a, runtime=operational_status(ctx.db, a))}
    elif action in {"activate", "restart"}:
        if st == "archived":
            raise HTTPException(400, "Archived agents cannot be activated. Duplicate it instead.")
        if action == "restart" and st != "paused":
            raise HTTPException(400, "Only paused agents can be restarted")
        if not a.last_test_ok:
            raise HTTPException(400, "This agent has not passed a live test. Run TEST successfully first "
                                     "(requires a connected AI provider).")
        a.status = "active"
    elif action == "pause":
        if st != "active":
            raise HTTPException(400, "Only active agents can be paused")
        a.status = "paused"
    elif action == "archive":
        a.status = "archived"
        for t in ctx.db.scalars(select(m.Task).where(m.Task.assignee_agent_id == a.id, m.Task.status.in_(["todo", "in_progress"]))):
            t.assignee_agent_id = None  # return queued work to humans
    elif action == "duplicate":
        clone = m.Agent(**{k: getattr(a, k) for k in AgentPatch.model_fields if hasattr(a, k)},
                        company_id=a.company_id, code=_code(ctx.db, a.company_id, a.name + " copy"),
                        status="configured" if a.instructions else "draft")
        clone.name = f"{a.name} (copy)"
        ctx.db.add(clone)
        ctx.db.flush()
        ctx.audit("agent.duplicate", "agent", clone.id, a.company_id, source=str(a.id))
        ctx.db.commit()
        return row(clone, runtime=operational_status(ctx.db, clone))
    else:
        raise HTTPException(404, "Unknown lifecycle action")
    ctx.audit(f"agent.{action}", "agent", a.id, a.company_id, from_status=st, to_status=a.status)
    ctx.db.commit()
    return row(a, runtime=operational_status(ctx.db, a))
