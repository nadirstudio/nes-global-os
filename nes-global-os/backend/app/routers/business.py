"""CRM (multi-company pipelines), projects, finance."""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from .. import models as m
from ..config import settings
from ..deps import Ctx, ensure_company, require
from ..intelligence import OPEN
from ..util import apply, get_or_404, row

router = APIRouter(tags=["business"])


def _scoped(ctx: Ctx, q, col):
    if ctx.scope.company_ids is not None:
        q = q.where(col.in_(ctx.scope.company_ids or {uuid.uuid4()}))
    return q


def norm_phone(p: str | None) -> str | None:
    if not p:
        return None
    d = re.sub(r"\D", "", p)
    if d.startswith("0") and len(d) == 11:
        d = "92" + d[1:]  # Pakistani mobile 03xx → 923xx
    return "+" + d if d else None


# ================================================================ CRM
class PipelineIn(BaseModel):
    company_id: uuid.UUID
    name: str
    stages: list[str] = Field(min_length=2)


@router.get("/crm/pipelines")
def pipelines(ctx: Ctx = Depends(require("crm.view"))):
    return [row(p) for p in ctx.db.scalars(_scoped(ctx, select(m.Pipeline), m.Pipeline.company_id))]


@router.post("/crm/pipelines", status_code=201)
def create_pipeline(body: PipelineIn, ctx: Ctx = Depends(require("department.manage"))):
    ensure_company(ctx, body.company_id)
    p = m.Pipeline(**body.model_dump())
    ctx.db.add(p)
    ctx.db.flush()
    ctx.audit("pipeline.create", "pipeline", p.id, p.company_id, name=p.name)
    ctx.db.commit()
    return row(p)


class LeadIn(BaseModel):
    company_id: uuid.UUID
    pipeline_id: uuid.UUID | None = None
    name: str
    phone: str | None = None
    email: str | None = None
    source: str | None = None
    service: str | None = None
    value: Decimal | None = None
    currency: str = "PKR"
    owner_person_id: uuid.UUID | None = None
    next_follow_up: datetime | None = None
    notes: str | None = None


class LeadPatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    source: str | None = None
    service: str | None = None
    value: Decimal | None = None
    currency: str | None = None
    owner_person_id: uuid.UUID | None = None
    next_follow_up: datetime | None = None
    notes: str | None = None
    stage: str | None = None
    status: str | None = None


def score_lead(db, lead: m.Lead) -> int:
    """Transparent rule-based score (0-100). Agents may suggest changes; the rules stay auditable."""
    s = 0
    s += 20 if lead.phone else 0
    s += 10 if lead.email else 0
    s += 15 if lead.service else 0
    s += 20 if lead.value else 0
    s += 10 if (lead.source or "").lower() in {"referral", "walk-in", "office visit", "repeat"} else 0
    s += 10 if lead.next_follow_up else 0
    if lead.id:
        acts = db.scalar(select(func.count()).where(m.Activity.lead_id == lead.id)) or 0
        s += min(15, acts * 5)
    return min(100, s)


def _visible_lead(ctx: Ctx, l: m.Lead) -> bool:
    if not ctx.scope.allows_company(l.company_id):
        return False
    if ctx.scope.own_only:
        return l.owner_person_id == ctx.user.person_id
    return True


@router.get("/crm/leads")
def leads(company_id: uuid.UUID | None = None, status: str = "open", q: str | None = None,
          ctx: Ctx = Depends(require("crm.view"))):
    query = _scoped(ctx, select(m.Lead), m.Lead.company_id).order_by(m.Lead.updated_at.desc()).limit(1000)
    if company_id:
        query = query.where(m.Lead.company_id == company_id)
    if status != "all":
        query = query.where(m.Lead.status == status)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(m.Lead.name).like(like), m.Lead.phone.like(like), func.lower(m.Lead.email).like(like)))
    return [row(l) for l in ctx.db.scalars(query) if _visible_lead(ctx, l)]


@router.post("/crm/leads", status_code=201)
def create_lead(body: LeadIn, ctx: Ctx = Depends(require("crm.manage"))):
    ensure_company(ctx, body.company_id)
    data = body.model_dump()
    data["phone"] = norm_phone(body.phone)
    data["email"] = body.email.strip().lower() if body.email else None
    # duplicate protection: one open lead per contact per company
    conds = [c for c in [m.Lead.phone == data["phone"] if data["phone"] else None,
                         m.Lead.email == data["email"] if data["email"] else None] if c is not None]
    if conds:
        dup = ctx.db.scalar(select(m.Lead).where(m.Lead.company_id == body.company_id, m.Lead.status == "open", or_(*conds)))
        if dup:
            raise HTTPException(409, detail={"message": f"An open lead for this contact already exists ({dup.name}).",
                                             "existing_id": str(dup.id)})
    pipe = ctx.db.get(m.Pipeline, body.pipeline_id) if body.pipeline_id else \
        ctx.db.scalar(select(m.Pipeline).where(m.Pipeline.company_id == body.company_id))
    if not pipe or pipe.company_id != body.company_id:
        raise HTTPException(400, "This company has no sales pipeline yet")
    data["pipeline_id"] = pipe.id
    if not data["owner_person_id"] and ctx.user.person_id:
        data["owner_person_id"] = ctx.user.person_id
    l = m.Lead(**data, stage=pipe.stages[0])
    ctx.db.add(l)
    ctx.db.flush()
    l.score = score_lead(ctx.db, l)
    ctx.audit("lead.create", "lead", l.id, l.company_id, name=l.name, source=l.source)
    ctx.db.commit()
    return row(l)


@router.patch("/crm/leads/{lid}")
def update_lead(lid: str, body: LeadPatch, ctx: Ctx = Depends(require("crm.manage"))):
    l = get_or_404(ctx.db, m.Lead, lid, "Lead")
    if not _visible_lead(ctx, l):
        raise HTTPException(403, "Not your lead")
    data = body.model_dump(exclude_unset=True)
    if "phone" in data:
        data["phone"] = norm_phone(data["phone"])
    if "stage" in data:
        pipe = ctx.db.get(m.Pipeline, l.pipeline_id)
        if data["stage"] not in pipe.stages:
            raise HTTPException(400, f"Stage must be one of {pipe.stages}")
    if data.get("status") and data["status"] not in {"open", "won", "lost"}:
        raise HTTPException(400, "Status must be open, won or lost")
    changed = apply(l, data, set(LeadPatch.model_fields))
    if l.status == "won" and not l.customer_id:
        cust = None
        if l.phone or l.email:
            cust = ctx.db.scalar(select(m.Customer).where(m.Customer.company_id == l.company_id,
                                                          or_(*[c for c in [m.Customer.phone == l.phone if l.phone else None,
                                                                            m.Customer.email == l.email if l.email else None] if c is not None])))
        if not cust:
            cust = m.Customer(company_id=l.company_id, name=l.name, phone=l.phone, email=l.email)
            ctx.db.add(cust)
            ctx.db.flush()
        l.customer_id = cust.id
    l.score = score_lead(ctx.db, l)
    ctx.audit("lead.update", "lead", l.id, l.company_id, **{k: str(v) for k, v in changed.items()})
    ctx.db.commit()
    return row(l)


class ActivityIn(BaseModel):
    lead_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    channel: str
    direction: str = "out"
    summary: str


@router.post("/crm/activities", status_code=201)
def add_activity(body: ActivityIn, ctx: Ctx = Depends(require("crm.manage"))):
    if body.channel not in {"call", "whatsapp", "email", "visit", "note", "meeting"}:
        raise HTTPException(400, "Unknown channel")
    target = ctx.db.get(m.Lead, body.lead_id) if body.lead_id else ctx.db.get(m.Customer, body.customer_id) if body.customer_id else None
    if not target:
        raise HTTPException(400, "Provide a lead_id or customer_id")
    ensure_company(ctx, target.company_id)
    a = m.Activity(**body.model_dump(), company_id=target.company_id, by_user_id=ctx.user.id)
    ctx.db.add(a)
    if isinstance(target, m.Lead):
        ctx.db.flush()
        target.score = score_lead(ctx.db, target)
    ctx.db.commit()
    return row(a)


@router.get("/crm/history")
def history(lead_id: uuid.UUID | None = None, customer_id: uuid.UUID | None = None, ctx: Ctx = Depends(require("crm.view"))):
    q = select(m.Activity).order_by(m.Activity.at.desc()).limit(200)
    if lead_id:
        l = get_or_404(ctx.db, m.Lead, lead_id, "Lead")
        ensure_company(ctx, l.company_id)
        conds = [m.Activity.lead_id == lead_id] + ([m.Activity.customer_id == l.customer_id] if l.customer_id else [])
        q = q.where(or_(*conds))
    elif customer_id:
        c = get_or_404(ctx.db, m.Customer, customer_id, "Customer")
        ensure_company(ctx, c.company_id)
        q = q.where(m.Activity.customer_id == customer_id)
    else:
        raise HTTPException(400, "lead_id or customer_id required")
    return [row(a) for a in ctx.db.scalars(q)]


@router.get("/crm/customers")
def customers(company_id: uuid.UUID | None = None, ctx: Ctx = Depends(require("crm.view"))):
    q = _scoped(ctx, select(m.Customer), m.Customer.company_id).order_by(m.Customer.created_at.desc()).limit(1000)
    if company_id:
        q = q.where(m.Customer.company_id == company_id)
    return [row(c) for c in ctx.db.scalars(q)]


# ================================================================ projects
class ProjectIn(BaseModel):
    company_id: uuid.UUID
    name: str
    kind: str = "internal"
    manager_person_id: uuid.UUID | None = None
    objectives: str | None = None
    budget: Decimal | None = None
    currency: str = "PKR"
    status: str = "planning"
    start_on: date | None = None
    deadline: date | None = None
    member_ids: list[str] = []
    agent_ids: list[str] = []


class ProjectPatch(BaseModel):
    name: str | None = None
    kind: str | None = None
    manager_person_id: uuid.UUID | None = None
    objectives: str | None = None
    budget: Decimal | None = None
    status: str | None = None
    start_on: date | None = None
    deadline: date | None = None
    member_ids: list[str] | None = None
    agent_ids: list[str] | None = None


def _project_view(ctx: Ctx, p: m.Project) -> dict:
    db = ctx.db
    tasks = list(db.scalars(select(m.Task).where(m.Task.project_id == p.id)))
    now = datetime.now(timezone.utc)
    fin = dict(db.execute(select(m.FinanceEntry.kind, func.sum(m.FinanceEntry.amount * m.FinanceEntry.fx_to_pkr))
                          .where(m.FinanceEntry.project_id == p.id).group_by(m.FinanceEntry.kind)).all())
    ms = list(db.scalars(select(m.Milestone).where(m.Milestone.project_id == p.id).order_by(m.Milestone.due_on.nulls_last())))
    spent = float(fin.get("expense") or 0)
    return row(p, milestones=[row(x) for x in ms],
               stats={"tasks": len(tasks), "done": sum(t.status == "done" for t in tasks),
                      "open": sum(t.status in OPEN for t in tasks),
                      "overdue": sum(1 for t in tasks if t.status in OPEN and t.due_at and t.due_at < now),
                      "revenue_pkr": float(fin.get("revenue") or 0), "expenses_pkr": spent,
                      "budget_used_pct": round(100 * spent / float(p.budget)) if p.budget else None})


@router.get("/projects")
def list_projects(ctx: Ctx = Depends(require("projects.view"))):
    q = _scoped(ctx, select(m.Project), m.Project.company_id).order_by(m.Project.deadline.nulls_last())
    out = []
    for p in ctx.db.scalars(q):
        if ctx.scope.own_only and str(ctx.user.person_id) not in (p.member_ids or []) and p.manager_person_id != ctx.user.person_id:
            continue
        out.append(_project_view(ctx, p))
    return out


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, ctx: Ctx = Depends(require("projects.manage"))):
    ensure_company(ctx, body.company_id)
    p = m.Project(**body.model_dump())
    ctx.db.add(p)
    ctx.db.flush()
    ctx.audit("project.create", "project", p.id, p.company_id, name=p.name)
    ctx.db.commit()
    return _project_view(ctx, p)


@router.patch("/projects/{pid}")
def update_project(pid: str, body: ProjectPatch, ctx: Ctx = Depends(require("projects.manage"))):
    p = get_or_404(ctx.db, m.Project, pid, "Project")
    ensure_company(ctx, p.company_id)
    changed = apply(p, body.model_dump(exclude_unset=True), set(ProjectPatch.model_fields))
    ctx.audit("project.update", "project", p.id, p.company_id, fields=sorted(changed))
    ctx.db.commit()
    return _project_view(ctx, p)


class MilestoneIn(BaseModel):
    title: str
    deliverable: str | None = None
    due_on: date | None = None
    done: bool = False


@router.post("/projects/{pid}/milestones", status_code=201)
def add_milestone(pid: str, body: MilestoneIn, ctx: Ctx = Depends(require("projects.manage"))):
    p = get_or_404(ctx.db, m.Project, pid, "Project")
    ensure_company(ctx, p.company_id)
    ms = m.Milestone(project_id=p.id, **body.model_dump())
    ctx.db.add(ms)
    ctx.db.commit()
    return row(ms)


@router.patch("/milestones/{mid}")
def toggle_milestone(mid: str, body: MilestoneIn, ctx: Ctx = Depends(require("projects.manage"))):
    ms = get_or_404(ctx.db, m.Milestone, mid, "Milestone")
    ensure_company(ctx, ctx.db.get(m.Project, ms.project_id).company_id)
    apply(ms, body.model_dump(), {"title", "deliverable", "due_on", "done"})
    ctx.db.commit()
    return row(ms)


# ================================================================ finance
class EntryIn(BaseModel):
    company_id: uuid.UUID
    project_id: uuid.UUID | None = None
    kind: str
    category: str | None = None
    service: str | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "PKR"
    fx_to_pkr: Decimal = Decimal(1)
    description: str | None = None
    reference: str | None = None
    occurred_on: date


@router.get("/finance/entries")
def entries(company_id: uuid.UUID | None = None, start: date | None = None, end: date | None = None,
            ctx: Ctx = Depends(require("finance.view"))):
    q = _scoped(ctx, select(m.FinanceEntry), m.FinanceEntry.company_id).order_by(m.FinanceEntry.occurred_on.desc()).limit(1000)
    if company_id:
        q = q.where(m.FinanceEntry.company_id == company_id)
    if start:
        q = q.where(m.FinanceEntry.occurred_on >= start)
    if end:
        q = q.where(m.FinanceEntry.occurred_on <= end)
    return [row(e) for e in ctx.db.scalars(q)]


@router.post("/finance/entries", status_code=201)
def add_entry(body: EntryIn, ctx: Ctx = Depends(require("finance.manage"))):
    ensure_company(ctx, body.company_id)
    if body.kind not in {"revenue", "expense"}:
        raise HTTPException(400, "kind must be revenue or expense")
    if body.currency == settings.default_currency and body.fx_to_pkr != 1:
        raise HTTPException(400, "PKR entries must use fx_to_pkr = 1")
    e = m.FinanceEntry(**body.model_dump(), created_by_user_id=ctx.user.id)
    ctx.db.add(e)
    ctx.db.flush()
    ctx.audit("finance.entry", "finance_entry", e.id, e.company_id, kind=e.kind, amount=str(e.amount), currency=e.currency)
    ctx.db.commit()
    return row(e)


@router.get("/finance/summary")
def summary(start: date | None = None, end: date | None = None, ctx: Ctx = Depends(require("finance.view"))):
    today = datetime.now(settings.tz).date()
    start = start or today.replace(day=1)
    end = end or today
    q = _scoped(ctx, select(m.Company.name, m.FinanceEntry.kind, func.sum(m.FinanceEntry.amount * m.FinanceEntry.fx_to_pkr))
                .select_from(m.FinanceEntry).join(m.Company, m.Company.id == m.FinanceEntry.company_id)
                .where(m.FinanceEntry.occurred_on.between(start, end))
                .group_by(m.Company.name, m.FinanceEntry.kind), m.FinanceEntry.company_id)
    by = {}
    for name, kind, total in ctx.db.execute(q):
        by.setdefault(name, {"revenue": 0.0, "expense": 0.0})[kind] = float(total)
    services = _scoped(ctx, select(m.FinanceEntry.service, func.sum(m.FinanceEntry.amount * m.FinanceEntry.fx_to_pkr))
                       .where(m.FinanceEntry.kind == "revenue", m.FinanceEntry.service.is_not(None),
                              m.FinanceEntry.occurred_on.between(start, end))
                       .group_by(m.FinanceEntry.service), m.FinanceEntry.company_id)
    return {"start": start, "end": end, "currency": "PKR",
            "by_company": [{"company": k, **v, "net": v["revenue"] - v["expense"]} for k, v in sorted(by.items())],
            "top_services": sorted([{"service": s, "revenue": float(t)} for s, t in ctx.db.execute(services)],
                                   key=lambda x: -x["revenue"])[:10]}


class InvoiceIn(BaseModel):
    company_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    amount: Decimal = Field(gt=0)
    currency: str = "PKR"
    issued_on: date | None = None
    due_on: date | None = None
    description: str | None = None


@router.get("/finance/invoices")
def invoices(ctx: Ctx = Depends(require("finance.view"))):
    q = _scoped(ctx, select(m.Invoice), m.Invoice.company_id).order_by(m.Invoice.issued_on.desc().nulls_last()).limit(500)
    return [row(i) for i in ctx.db.scalars(q)]


@router.post("/finance/invoices", status_code=201)
def create_invoice(body: InvoiceIn, ctx: Ctx = Depends(require("finance.manage"))):
    ensure_company(ctx, body.company_id)
    comp = ctx.db.get(m.Company, body.company_id)
    year = (body.issued_on or datetime.now(settings.tz).date()).year
    n = (ctx.db.scalar(select(func.count()).where(m.Invoice.company_id == body.company_id)) or 0) + 1
    number = f"{comp.code}-{year}-{n:04d}"
    while ctx.db.scalar(select(m.Invoice).where(m.Invoice.company_id == comp.id, m.Invoice.number == number)):
        n += 1
        number = f"{comp.code}-{year}-{n:04d}"
    data = body.model_dump()
    data["issued_on"] = body.issued_on or datetime.now(settings.tz).date()
    inv = m.Invoice(**data, number=number, status="issued")
    ctx.db.add(inv)
    ctx.db.flush()
    ctx.audit("invoice.create", "invoice", inv.id, inv.company_id, number=number, amount=str(inv.amount))
    ctx.db.commit()
    return row(inv)


class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    received_on: date | None = None
    reference: str | None = None
    fx_to_pkr: Decimal = Decimal(1)


@router.post("/finance/invoices/{iid}/payment")
def record_payment(iid: str, body: PaymentIn, ctx: Ctx = Depends(require("finance.manage"))):
    """Records money already received (a receipt). The system never moves money itself."""
    inv = get_or_404(ctx.db, m.Invoice, iid, "Invoice")
    ensure_company(ctx, inv.company_id)
    if inv.status in {"paid", "void"}:
        raise HTTPException(409, f"Invoice is {inv.status}")
    if inv.currency != settings.default_currency and body.fx_to_pkr == 1:
        raise HTTPException(400, f"Enter the exchange rate used to convert {inv.currency} to PKR")
    if inv.paid_amount + body.amount > inv.amount:
        raise HTTPException(400, "Payment exceeds the outstanding balance")
    inv.paid_amount += body.amount
    inv.status = "paid" if inv.paid_amount == inv.amount else "partial"
    ctx.db.add(m.FinanceEntry(company_id=inv.company_id, project_id=inv.project_id, kind="revenue",
                              category="invoice payment", amount=body.amount, currency=inv.currency,
                              fx_to_pkr=body.fx_to_pkr if inv.currency != settings.default_currency else Decimal(1),
                              reference=body.reference or inv.number,
                              description=f"Receipt for {inv.number}",
                              occurred_on=body.received_on or datetime.now(settings.tz).date(),
                              created_by_user_id=ctx.user.id))
    ctx.audit("invoice.payment", "invoice", inv.id, inv.company_id, amount=str(body.amount))
    ctx.db.commit()
    return row(inv)
