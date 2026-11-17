"""Companies, departments and the live organisational map."""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from .. import models as m
from ..ai.runtime import operational_status
from ..deps import Ctx, ensure_company, require
from ..util import apply, get_or_404, row

router = APIRouter(tags=["organisation"])


class CompanyIn(BaseModel):
    code: str
    name: str
    kind: str = "unit"
    parent_id: uuid.UUID | None = None
    description: str | None = None
    website: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    address: str | None = None
    services: list[str] = []
    status: str = "active"


class CompanyPatch(BaseModel):
    name: str | None = None
    kind: str | None = None
    description: str | None = None
    website: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    address: str | None = None
    services: list[str] | None = None
    status: str | None = None


def _code(s: str) -> str:
    c = re.sub(r"[^A-Z0-9-]", "", s.upper().replace(" ", "-"))
    if not c:
        raise HTTPException(400, "Code must contain letters or digits")
    return c[:32]


@router.get("/companies")
def list_companies(ctx: Ctx = Depends(require("tasks.view"))):
    q = select(m.Company).order_by((m.Company.kind != "parent"), m.Company.name)
    if ctx.scope.company_ids is not None:
        q = q.where(m.Company.id.in_(ctx.scope.company_ids or {uuid.uuid4()}))
    return [row(c) for c in ctx.db.scalars(q)]


@router.post("/companies", status_code=201)
def create_company(body: CompanyIn, ctx: Ctx = Depends(require("company.manage"))):
    code = _code(body.code)
    if ctx.db.scalar(select(m.Company).where(m.Company.code == code)):
        raise HTTPException(409, "A company with this code already exists")
    c = m.Company(**{**body.model_dump(), "code": code})
    ctx.db.add(c)
    ctx.db.flush()
    ctx.db.add(m.Pipeline(company_id=c.id, name="Sales", stages=["Inquiry", "Qualified", "Proposal", "Negotiation"]))
    ctx.audit("company.create", "company", c.id, c.id, name=c.name)
    ctx.db.commit()
    return row(c)


@router.patch("/companies/{cid}")
def update_company(cid: str, body: CompanyPatch, ctx: Ctx = Depends(require("company.manage"))):
    c = get_or_404(ctx.db, m.Company, cid, "Company")
    changed = apply(c, body.model_dump(exclude_unset=True), set(CompanyPatch.model_fields))
    ctx.audit("company.update", "company", c.id, c.id, **changed)
    ctx.db.commit()
    return row(c)


class DeptIn(BaseModel):
    company_id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    head_person_id: uuid.UUID | None = None
    is_group_wide: bool = False


class DeptPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    head_person_id: uuid.UUID | None = None
    status: str | None = None


@router.get("/departments")
def list_departments(company_id: uuid.UUID | None = None, ctx: Ctx = Depends(require("tasks.view"))):
    q = select(m.Department).order_by(m.Department.name)
    if company_id:
        ensure_company(ctx, company_id)
        q = q.where(m.Department.company_id == company_id)
    elif ctx.scope.company_ids is not None:
        q = q.where(m.Department.company_id.in_(ctx.scope.company_ids or {uuid.uuid4()}))
    return [row(d) for d in ctx.db.scalars(q)]


@router.post("/departments", status_code=201)
def create_department(body: DeptIn, ctx: Ctx = Depends(require("department.manage"))):
    ensure_company(ctx, body.company_id)
    get_or_404(ctx.db, m.Company, body.company_id, "Company")
    code = _code(body.code)
    if ctx.db.scalar(select(m.Department).where(m.Department.company_id == body.company_id, m.Department.code == code)):
        raise HTTPException(409, "This company already has a department with that code")
    d = m.Department(**{**body.model_dump(), "code": code})
    ctx.db.add(d)
    ctx.db.flush()
    ctx.audit("department.create", "department", d.id, d.company_id, name=d.name)
    ctx.db.commit()
    return row(d)


@router.patch("/departments/{did}")
def update_department(did: str, body: DeptPatch, ctx: Ctx = Depends(require("department.manage"))):
    d = get_or_404(ctx.db, m.Department, did, "Department")
    ensure_company(ctx, d.company_id)
    changed = apply(d, body.model_dump(exclude_unset=True), set(DeptPatch.model_fields))
    ctx.audit("department.update", "department", d.id, d.company_id, **changed)
    ctx.db.commit()
    return row(d)


@router.get("/org/tree")
def org_tree(ctx: Ctx = Depends(require("dashboard.view"))):
    """CEO → companies → departments → heads, people, AI agents."""
    db, sc = ctx.db, ctx.scope
    companies = [c for c in db.scalars(select(m.Company).order_by((m.Company.kind != "parent"), m.Company.name))
                 if sc.allows_company(c.id)]
    people = [p for p in db.scalars(select(m.Person).where(m.Person.status != "inactive")) if sc.allows_company(p.company_id)]
    agents = [a for a in db.scalars(select(m.Agent).where(m.Agent.status != "archived")) if sc.allows_company(a.company_id)]
    ceo_user = db.scalar(select(m.User).where(m.User.role == "ceo"))
    ceo = db.get(m.Person, ceo_user.person_id) if ceo_user and ceo_user.person_id else None

    def pnode(p):
        return {"type": "person", "id": str(p.id), "name": p.full_name, "designation": p.designation,
                "level": p.skill_level, "category": p.category, "status": p.status}

    def anode(a):
        st = operational_status(db, a)
        return {"type": "agent", "id": str(a.id), "name": a.name, "designation": a.designation,
                "lifecycle": a.status, "operational": st["operational"], "coordinator": a.is_coordinator,
                "model": a.model}

    out = []
    for c in companies:
        depts = list(db.scalars(select(m.Department).where(m.Department.company_id == c.id).order_by(m.Department.name)))
        dnodes = []
        for d in depts:
            if sc.department_ids is not None and d.id not in sc.department_ids:
                continue
            head = next((p for p in people if p.id == d.head_person_id), None)
            dnodes.append({
                "type": "department", "id": str(d.id), "name": d.name, "group_wide": d.is_group_wide,
                "head": pnode(head) if head else None,
                "people": [pnode(p) for p in people if p.department_id == d.id and p.id != d.head_person_id],
                "agents": sorted([anode(a) for a in agents if a.department_id == d.id],
                                 key=lambda x: (not x["coordinator"], x["name"])),
            })
        out.append({"type": "company", "id": str(c.id), "code": c.code, "name": c.name, "kind": c.kind,
                    "status": c.status, "parent_id": str(c.parent_id) if c.parent_id else None,
                    "directors": [pnode(p) for p in people if p.company_id == c.id and p.category == "director"
                                  and (not ceo or p.id != ceo.id)],
                    "unassigned_people": [pnode(p) for p in people if p.company_id == c.id and not p.department_id
                                          and p.category != "director" and (not ceo or p.id != ceo.id)],
                    "company_agents": [anode(a) for a in agents if a.company_id == c.id and not a.department_id],
                    "departments": dnodes})
    return {"ceo": pnode(ceo) if ceo else None, "companies": out}
