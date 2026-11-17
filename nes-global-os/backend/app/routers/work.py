"""Tasks, workforce intelligence, approvals."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from .. import models as m
from ..ai.runtime import run_agent
from ..deps import Ctx, ensure_company, ensure_department, require
from ..intelligence import OPEN, department_performance, workforce
from ..permissions import can
from ..util import apply, get_or_404, row

router = APIRouter(tags=["work"])

STATUSES = ["todo", "in_progress", "blocked", "review", "done", "cancelled"]


class TaskIn(BaseModel):
    company_id: uuid.UUID
    department_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    assignee_person_id: uuid.UUID | None = None
    assignee_agent_id: uuid.UUID | None = None
    reviewer_person_id: uuid.UUID | None = None
    priority: str = "medium"
    impact: str = "medium"
    complexity: str = "standard"
    required_skills: list[str] = []
    due_at: datetime | None = None
    estimated_hours: Decimal = Decimal(1)


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    department_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    assignee_person_id: uuid.UUID | None = None
    assignee_agent_id: uuid.UUID | None = None
    reviewer_person_id: uuid.UUID | None = None
    priority: str | None = None
    impact: str | None = None
    complexity: str | None = None
    required_skills: list[str] | None = None
    due_at: datetime | None = None
    estimated_hours: Decimal | None = None
    status: str | None = None
    result: str | None = None
    quality_score: int | None = Field(default=None, ge=1, le=5)
    customer_satisfaction: int | None = Field(default=None, ge=1, le=5)


OWN_FIELDS = {"status", "result"}


def _visible(ctx: Ctx, t: m.Task) -> bool:
    if ctx.scope.own_only:
        return t.assignee_person_id == ctx.user.person_id or t.reviewer_person_id == ctx.user.person_id
    if not ctx.scope.allows_company(t.company_id):
        return False
    if ctx.scope.department_ids is not None:
        return t.department_id in ctx.scope.department_ids or t.assignee_person_id == ctx.user.person_id
    return True


def _check_assignees(ctx: Ctx, company_id, person_id, agent_id, reviewer_id=None):
    if person_id:
        p = get_or_404(ctx.db, m.Person, person_id, "Assignee")
        if p.company_id != company_id and ctx.role != "ceo":
            raise HTTPException(400, "Assignee belongs to a different company")
        if p.status == "inactive":
            raise HTTPException(400, "Assignee is inactive")
    if agent_id:
        a = get_or_404(ctx.db, m.Agent, agent_id, "Agent")
        if a.company_id != company_id:
            raise HTTPException(400, "An agent can only work on its own company's tasks")
        if a.status == "archived":
            raise HTTPException(400, "Agent is archived")
    if person_id and agent_id:
        raise HTTPException(400, "Assign a task to a person or an agent, not both")


@router.get("/tasks")
def list_tasks(status: str | None = None, company_id: uuid.UUID | None = None, mine: bool = False,
               assignee_person_id: uuid.UUID | None = None, assignee_agent_id: uuid.UUID | None = None,
               project_id: uuid.UUID | None = None, overdue: bool = False, limit: int = 300,
               ctx: Ctx = Depends(require("tasks.view"))):
    q = select(m.Task)
    if status == "open":
        q = q.where(m.Task.status.in_(OPEN))
    elif status:
        q = q.where(m.Task.status == status)
    if company_id:
        q = q.where(m.Task.company_id == company_id)
    if mine:
        q = q.where(m.Task.assignee_person_id == ctx.user.person_id)
    if assignee_person_id:
        q = q.where(m.Task.assignee_person_id == assignee_person_id)
    if assignee_agent_id:
        q = q.where(m.Task.assignee_agent_id == assignee_agent_id)
    if project_id:
        q = q.where(m.Task.project_id == project_id)
    if overdue:
        q = q.where(m.Task.status.in_(OPEN), m.Task.due_at < datetime.now(timezone.utc))
    if ctx.scope.own_only:
        q = q.where(or_(m.Task.assignee_person_id == ctx.user.person_id, m.Task.reviewer_person_id == ctx.user.person_id))
    q = q.order_by(m.Task.due_at.nulls_last(), m.Task.created_at.desc()).limit(min(limit, 1000))
    now = datetime.now(timezone.utc)
    return [row(t, overdue=bool(t.status in OPEN and t.due_at and t.due_at < now))
            for t in ctx.db.scalars(q) if _visible(ctx, t)]


@router.get("/tasks/{tid}")
def get_task(tid: str, ctx: Ctx = Depends(require("tasks.view"))):
    t = get_or_404(ctx.db, m.Task, tid, "Task")
    if not _visible(ctx, t):
        raise HTTPException(403, "Not your task")
    names = {}
    for pid in (t.assignee_person_id, t.reviewer_person_id):
        if pid:
            p = ctx.db.get(m.Person, pid)
            names[str(pid)] = p.full_name if p else None
    agent = ctx.db.get(m.Agent, t.assignee_agent_id) if t.assignee_agent_id else None
    project = ctx.db.get(m.Project, t.project_id) if t.project_id else None
    now = datetime.now(timezone.utc)
    return row(t, overdue=bool(t.status in OPEN and t.due_at and t.due_at < now),
               assignee=names.get(str(t.assignee_person_id)) or (agent.name if agent else None),
               reviewer=names.get(str(t.reviewer_person_id)), project=project.name if project else None,
               can_review=can(ctx.role, "tasks.review") and not ctx.scope.own_only)


@router.post("/tasks", status_code=201)
def create_task(body: TaskIn, ctx: Ctx = Depends(require("tasks.create"))):
    if ctx.scope.department_ids is not None:
        ensure_department(ctx, body.company_id, body.department_id)
    else:
        ensure_company(ctx, body.company_id)
    _check_assignees(ctx, body.company_id, body.assignee_person_id, body.assignee_agent_id)
    t = m.Task(**body.model_dump(), created_by_user_id=ctx.user.id)
    ctx.db.add(t)
    ctx.db.flush()
    ctx.audit("task.create", "task", t.id, t.company_id, title=t.title)
    ctx.db.commit()
    return row(t)


@router.patch("/tasks/{tid}")
def update_task(tid: str, body: TaskPatch, ctx: Ctx = Depends(require("tasks.update_own"))):
    t = get_or_404(ctx.db, m.Task, tid, "Task")
    if not _visible(ctx, t):
        raise HTTPException(403, "Not your task")
    data = body.model_dump(exclude_unset=True)
    is_leader = can(ctx.role, "tasks.review") and not ctx.scope.own_only
    if not is_leader:
        extra = set(data) - OWN_FIELDS
        if extra:
            raise HTTPException(403, f"You can only update status and result (not {', '.join(sorted(extra))})")
        if data.get("status") == "done" and t.reviewer_person_id and t.reviewer_person_id != ctx.user.person_id:
            data["status"] = "review"  # supervised work goes to the reviewer first
    if "status" in data and data["status"] not in STATUSES:
        raise HTTPException(400, f"Status must be one of {STATUSES}")
    if {"assignee_person_id", "assignee_agent_id"} & set(data):
        # Assigning to one kind of worker releases the other.
        if data.get("assignee_person_id") and "assignee_agent_id" not in data:
            data["assignee_agent_id"] = None
        if data.get("assignee_agent_id") and "assignee_person_id" not in data:
            data["assignee_person_id"] = None
        _check_assignees(ctx, t.company_id, data.get("assignee_person_id", t.assignee_person_id),
                         data.get("assignee_agent_id", t.assignee_agent_id))
    old = t.status
    changed = apply(t, data, set(TaskPatch.model_fields))
    if t.status == "done" and old != "done":
        t.completed_at = datetime.now(timezone.utc)
    elif t.status != "done":
        t.completed_at = None
    ctx.audit("task.update", "task", t.id, t.company_id, **{k: str(v) for k, v in changed.items()})
    ctx.db.commit()
    return row(t)


@router.post("/tasks/{tid}/run-agent")
def run_task_agent(tid: str, ctx: Ctx = Depends(require("agents.run"))):
    t = get_or_404(ctx.db, m.Task, tid, "Task")
    ensure_company(ctx, t.company_id)
    if not t.assignee_agent_id:
        raise HTTPException(400, "This task is not assigned to an AI agent")
    a = ctx.db.get(m.Agent, t.assignee_agent_id)
    return _execute_agent_task(ctx.db, a, t, ctx.user.id)


def _execute_agent_task(db, a: m.Agent, t: m.Task, actor=None) -> dict:
    t.status = "in_progress"
    run = run_agent(db, a, f"Task: {t.title}\n\nDetails: {t.description or '-'}\n\n"
                           "Complete the task. Produce the deliverable text. If you need data you do not have, "
                           "list exactly what is missing.", "task", task=t, actor_user_id=actor)
    if run.status == "succeeded":
        t.result = run.output
        t.status = "review"  # agent output is always reviewed by a human before it counts as done
        if not t.reviewer_person_id:
            t.reviewer_person_id = a.supervisor_person_id
    else:
        t.status = "blocked" if run.status == "blocked" else "todo"
        t.result = f"Agent could not run: {run.error}"
    db.commit()
    return {"task": row(t), "run": row(run)}


# ---------------------------------------------------------------- workforce intelligence
@router.get("/workforce")
def workforce_view(ctx: Ctx = Depends(require("workforce.intelligence"))):
    return {"workforce": workforce(ctx.db, ctx.scope), "departments": department_performance(ctx.db, ctx.scope)}


class ApplyIn(BaseModel):
    task_id: uuid.UUID
    person_id: uuid.UUID


@router.post("/workforce/apply")
def apply_recommendation(body: ApplyIn, ctx: Ctx = Depends(require("tasks.review"))):
    """A department head reviews and accepts a recommendation. Nothing is auto-assigned."""
    t = get_or_404(ctx.db, m.Task, body.task_id, "Task")
    if ctx.scope.department_ids is not None:
        ensure_department(ctx, t.company_id, t.department_id)
    else:
        ensure_company(ctx, t.company_id)
    p = get_or_404(ctx.db, m.Person, body.person_id, "Person")
    _check_assignees(ctx, t.company_id, p.id, None)
    t.assignee_person_id = p.id
    if p.skill_level == "beginner" and not t.reviewer_person_id:
        t.reviewer_person_id = p.manager_id or ctx.user.person_id
    ctx.audit("task.assign", "task", t.id, t.company_id, person=p.full_name, via="recommendation")
    ctx.db.commit()
    return row(t)


# ---------------------------------------------------------------- approvals
@router.get("/approvals")
def list_approvals(status: str = "pending", ctx: Ctx = Depends(require("approvals.view"))):
    q = select(m.Approval).order_by(m.Approval.created_at.desc()).limit(200)
    if status != "all":
        q = q.where(m.Approval.status == status)
    out = []
    for a in ctx.db.scalars(q):
        if a.company_id and not ctx.scope.allows_company(a.company_id):
            continue
        agent = ctx.db.get(m.Agent, a.requested_by_agent_id) if a.requested_by_agent_id else None
        out.append(row(a, requested_by=agent.name if agent else None))
    return out


class DecideIn(BaseModel):
    decision: str  # approved | rejected
    note: str | None = None


@router.post("/approvals/{aid}/decide")
def decide(aid: str, body: DecideIn, ctx: Ctx = Depends(require("approvals.decide"))):
    a = get_or_404(ctx.db, m.Approval, aid, "Approval")
    if a.company_id:
        ensure_company(ctx, a.company_id)
    if a.status != "pending":
        raise HTTPException(409, f"Already {a.status}")
    if body.decision not in {"approved", "rejected"}:
        raise HTTPException(400, "Decision must be approved or rejected")
    a.status, a.decided_by_user_id, a.decided_at, a.decision_note = (
        body.decision, ctx.user.id, datetime.now(timezone.utc), body.note)
    ctx.audit(f"approval.{body.decision}", "approval", a.id, a.company_id, kind=a.kind, title=a.title)
    ctx.db.commit()
    # Approval only records the human decision. Outbound execution (email, WhatsApp...) happens
    # through the matching integration once connected, which checks this approved record first.
    return row(a)
