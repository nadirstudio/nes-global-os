"""Human workforce: profiles, accounts, onboarding/skill assessment, attendance."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .. import models as m
from ..config import settings
from ..deps import Ctx, current_ctx, ensure_department, require
from ..intelligence import OPEN, local_today
from ..permissions import ROLES
from ..security import hash_password, validate_password_strength
from ..util import apply, get_or_404, row

router = APIRouter(tags=["workforce"])

CATEGORIES = ["permanent", "part_time", "intern", "volunteer", "freelancer", "contractor", "remote",
              "project_based", "commission_sales", "white_label_partner", "collaborator", "director",
              "department_head", "manager", "trainee"]
LEVELS = ["beginner", "intermediate", "expert", "team_leader", "department_head"]

# What each level is allowed to receive (used by onboarding + workforce engine)
LEVEL_GUIDE = {
    "beginner": "Training plan plus basic, supervised assignments with a named reviewer.",
    "intermediate": "Standard operational responsibilities.",
    "expert": "Complex assignments; may mentor beginners.",
    "team_leader": "Complex work plus coordination of a small team.",
    "department_head": "Manages people, processes and the department's AI agents.",
}


class PersonIn(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    category: str = "permanent"
    designation: str | None = None
    company_id: uuid.UUID
    department_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    skill_level: str = "beginner"
    skills: list[str] = []
    experience_years: Decimal = Decimal(0)
    weekly_capacity_hours: Decimal = Decimal(48)
    responsibilities: str | None = None
    training_requirements: list[str] = []
    joined_on: date | None = None
    status: str = "onboarding"


class PersonPatch(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    category: str | None = None
    designation: str | None = None
    department_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    skill_level: str | None = None
    skills: list[str] | None = None
    experience_years: Decimal | None = None
    weekly_capacity_hours: Decimal | None = None
    responsibilities: str | None = None
    training_requirements: list[str] | None = None
    training_completed: list[str] | None = None
    achievements: list[str] | None = None
    status: str | None = None


def _validate(category: str | None, level: str | None) -> None:
    if category and category not in CATEGORIES:
        raise HTTPException(400, f"Unknown category. Use one of: {', '.join(CATEGORIES)}")
    if level and level not in LEVELS:
        raise HTTPException(400, f"Unknown skill level. Use one of: {', '.join(LEVELS)}")


def _next_code(db, company_id) -> str:
    comp = db.get(m.Company, company_id)
    prefix = (comp.code if comp else "NES").split("-")[-1][:5]
    n = db.scalar(select(func.count()).select_from(m.Person)) or 0
    while True:
        n += 1
        code = f"{prefix}-{n:04d}"
        if not db.scalar(select(m.Person).where(m.Person.employee_code == code)):
            return code


@router.get("/meta/workforce")
def meta(ctx: Ctx = Depends(current_ctx)):
    return {"categories": CATEGORIES, "levels": LEVELS, "level_guide": LEVEL_GUIDE, "roles": ROLES}


@router.get("/people")
def list_people(company_id: uuid.UUID | None = None, department_id: uuid.UUID | None = None,
                include_inactive: bool = False, ctx: Ctx = Depends(require("people.view"))):
    q = select(m.Person).order_by(m.Person.full_name)
    if not include_inactive:
        q = q.where(m.Person.status != "inactive")
    if company_id:
        q = q.where(m.Person.company_id == company_id)
    if department_id:
        q = q.where(m.Person.department_id == department_id)
    users = {u.person_id: u for u in ctx.db.scalars(select(m.User).where(m.User.person_id.is_not(None)))}
    out = []
    for p in ctx.db.scalars(q):
        if not ctx.scope.allows_company(p.company_id):
            continue
        if ctx.scope.department_ids is not None and p.department_id not in ctx.scope.department_ids:
            continue
        u = users.get(p.id)
        out.append(row(p, account={"email": u.email, "role": u.role, "active": u.is_active,
                                   "mfa": u.mfa_enabled} if u else None))
    return out


@router.get("/people/{pid}")
def get_person(pid: str, ctx: Ctx = Depends(current_ctx)):
    p = get_or_404(ctx.db, m.Person, pid, "Person")
    if p.id != ctx.user.person_id:
        if ctx.role not in {"ceo", "director", "dept_head", "manager"}:
            raise HTTPException(403, "You can only view your own profile")
        ensure_department(ctx, p.company_id, p.department_id)
    tasks = list(ctx.db.scalars(select(m.Task).where(m.Task.assignee_person_id == p.id)
                                .order_by(m.Task.due_at.nulls_last()).limit(50)))
    att = list(ctx.db.scalars(select(m.Attendance).where(m.Attendance.person_id == p.id)
                              .order_by(m.Attendance.day.desc()).limit(30)))
    u = ctx.db.scalar(select(m.User).where(m.User.person_id == p.id))
    supervised = list(ctx.db.scalars(select(m.Agent).where(m.Agent.supervisor_person_id == p.id)))
    return row(p, tasks=[row(t) for t in tasks], attendance=[row(a) for a in att],
               open_tasks=sum(t.status in OPEN for t in tasks),
               account={"email": u.email, "role": u.role, "active": u.is_active, "mfa": u.mfa_enabled} if u else None,
               supervised_agents=[{"id": str(a.id), "name": a.name, "status": a.status} for a in supervised],
               level_guide=LEVEL_GUIDE.get(p.skill_level))


@router.post("/people", status_code=201)
def create_person(body: PersonIn, ctx: Ctx = Depends(require("people.manage"))):
    _validate(body.category, body.skill_level)
    ensure_department(ctx, body.company_id, body.department_id) if ctx.scope.department_ids is not None \
        else ensure_department(ctx, body.company_id, None)
    data = body.model_dump()
    p = m.Person(**data, employee_code=_next_code(ctx.db, body.company_id))
    ctx.db.add(p)
    ctx.db.flush()
    _onboarding_tasks(ctx, p)
    ctx.audit("person.create", "person", p.id, p.company_id, name=p.full_name, level=p.skill_level)
    ctx.db.commit()
    return row(p)


def _onboarding_tasks(ctx: Ctx, p: m.Person) -> None:
    """Real onboarding work items created for the new person and their manager (not busywork)."""
    reviewer = p.manager_id
    items = [("Complete profile, skills self-assessment and document submission", "basic", 2)]
    for t in p.training_requirements or []:
        items.append((f"Training: {t}", "basic", 4))
    if p.skill_level == "beginner":
        items.append(("Shadow a senior team member on live work (supervised)", "basic", 8))
    for title, cx, hrs in items:
        ctx.db.add(m.Task(company_id=p.company_id, department_id=p.department_id, title=title,
                          assignee_person_id=p.id, reviewer_person_id=reviewer, complexity=cx,
                          estimated_hours=hrs, priority="high", created_by_user_id=ctx.user.id))
    if reviewer:
        ctx.db.add(m.Task(company_id=p.company_id, department_id=p.department_id,
                          title=f"Run skill assessment for {p.full_name} and confirm skill level",
                          assignee_person_id=reviewer, estimated_hours=1, priority="high",
                          created_by_user_id=ctx.user.id))


@router.patch("/people/{pid}")
def update_person(pid: str, body: PersonPatch, ctx: Ctx = Depends(require("people.manage"))):
    p = get_or_404(ctx.db, m.Person, pid, "Person")
    ensure_department(ctx, p.company_id, p.department_id) if ctx.scope.department_ids is not None \
        else ensure_department(ctx, p.company_id, None)
    data = body.model_dump(exclude_unset=True)
    _validate(data.get("category"), data.get("skill_level"))
    changed = apply(p, data, set(PersonPatch.model_fields))
    ctx.audit("person.update", "person", p.id, p.company_id, **{k: str(v) for k, v in changed.items()})
    ctx.db.commit()
    return row(p)


class AccountIn(BaseModel):
    email: str
    role: str
    temporary_password: str = Field(min_length=10)
    extra_company_ids: list[uuid.UUID] = []


@router.post("/people/{pid}/account", status_code=201)
def create_account(pid: str, body: AccountIn, ctx: Ctx = Depends(require("users.manage"))):
    p = get_or_404(ctx.db, m.Person, pid, "Person")
    if body.role not in ROLES or body.role == "ceo":
        raise HTTPException(400, "Invalid role")
    err = validate_password_strength(body.temporary_password)
    if err:
        raise HTTPException(400, err)
    if ctx.db.scalar(select(m.User).where(func.lower(m.User.email) == body.email.lower())):
        raise HTTPException(409, "That email already has an account")
    if ctx.db.scalar(select(m.User).where(m.User.person_id == p.id)):
        raise HTTPException(409, "This person already has an account")
    u = m.User(email=body.email.lower(), role=body.role, person_id=p.id,
               password_hash=hash_password(body.temporary_password))
    ctx.db.add(u)
    ctx.db.flush()
    for cid in body.extra_company_ids:
        ctx.db.add(m.UserCompanyAccess(user_id=u.id, company_id=cid))
    ctx.audit("user.create", "user", u.id, p.company_id, email=u.email, role=u.role)
    ctx.db.commit()
    return {"ok": True, "user_id": str(u.id)}


class AccountPatch(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    reset_password: str | None = None


@router.patch("/people/{pid}/account")
def update_account(pid: str, body: AccountPatch, ctx: Ctx = Depends(require("users.manage"))):
    u = ctx.db.scalar(select(m.User).where(m.User.person_id == uuid.UUID(pid)))
    if not u:
        raise HTTPException(404, "No account for this person")
    if u.role == "ceo" and (body.role or body.is_active is False):
        raise HTTPException(400, "The CEO account cannot be demoted or disabled here")
    if body.role:
        if body.role not in ROLES or body.role == "ceo":
            raise HTTPException(400, "Invalid role")
        u.role = body.role
        u.token_version += 1
    if body.is_active is not None:
        u.is_active = body.is_active
        u.token_version += 1
    if body.reset_password:
        err = validate_password_strength(body.reset_password)
        if err:
            raise HTTPException(400, err)
        u.password_hash = hash_password(body.reset_password)
        u.token_version += 1
    ctx.audit("user.update", "user", u.id, None, role=body.role, active=body.is_active,
              password_reset=bool(body.reset_password))
    ctx.db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- attendance
@router.post("/attendance/check-in")
def check_in(ctx: Ctx = Depends(current_ctx)):
    if not ctx.user.person_id:
        raise HTTPException(400, "Your account is not linked to a staff profile")
    from ..ai.runtime import get_setting
    from .mobile import ATTENDANCE_POLICY_DEFAULT
    pol = get_setting(ctx.db, "attendance_policy", ATTENDANCE_POLICY_DEFAULT)
    if not pol["allow_web_checkin_with_sites"] and ctx.db.scalar(select(m.WorkSite.id).where(m.WorkSite.active.is_(True)).limit(1)):
        raise HTTPException(400, "Office locations are set up, so check in with the NES Team app on your phone "
                                 "(GPS + fingerprint).")
    now_local = datetime.now(settings.tz)
    today = now_local.date()
    rec = ctx.db.scalar(select(m.Attendance).where(m.Attendance.person_id == ctx.user.person_id, m.Attendance.day == today))
    if rec and rec.check_in:
        raise HTTPException(409, "Already checked in today")
    start = datetime.combine(today, time(9, 0), tzinfo=settings.tz)
    status = "late" if now_local > start.replace(minute=15) else "present"
    if not rec:
        rec = m.Attendance(person_id=ctx.user.person_id, day=today)
        ctx.db.add(rec)
    rec.check_in, rec.status, rec.method = datetime.now(timezone.utc), status, "web"
    ctx.audit("attendance.check_in", "person", ctx.user.person_id, None, status=status)
    ctx.db.commit()
    return row(rec)


@router.post("/attendance/check-out")
def check_out(ctx: Ctx = Depends(current_ctx)):
    rec = ctx.db.scalar(select(m.Attendance).where(m.Attendance.person_id == ctx.user.person_id,
                                                   m.Attendance.day == local_today()))
    if not rec or not rec.check_in:
        raise HTTPException(400, "You have not checked in today")
    rec.check_out = datetime.now(timezone.utc)
    ctx.db.commit()
    return row(rec)


class MarkIn(BaseModel):
    person_id: uuid.UUID
    day: date | None = None
    status: str
    note: str | None = None


@router.post("/attendance/mark")
def mark(body: MarkIn, ctx: Ctx = Depends(require("attendance.manage"))):
    if body.status not in {"present", "late", "leave", "absent", "remote"}:
        raise HTTPException(400, "Invalid status")
    p = get_or_404(ctx.db, m.Person, body.person_id, "Person")
    ensure_department(ctx, p.company_id, p.department_id) if ctx.scope.department_ids is not None \
        else ensure_department(ctx, p.company_id, None)
    day = body.day or local_today()
    rec = ctx.db.scalar(select(m.Attendance).where(m.Attendance.person_id == p.id, m.Attendance.day == day))
    if not rec:
        rec = m.Attendance(person_id=p.id, day=day)
        ctx.db.add(rec)
    rec.status, rec.note = body.status, body.note
    ctx.audit("attendance.mark", "person", p.id, p.company_id, day=str(day), status=body.status)
    ctx.db.commit()
    return row(rec)


@router.get("/attendance")
def attendance(day: date | None = None, ctx: Ctx = Depends(require("attendance.manage"))):
    day = day or local_today()
    recs = {a.person_id: a for a in ctx.db.scalars(select(m.Attendance).where(m.Attendance.day == day))}
    out = []
    for p in ctx.db.scalars(select(m.Person).where(m.Person.status != "inactive").order_by(m.Person.full_name)):
        if not ctx.scope.allows_company(p.company_id):
            continue
        if ctx.scope.department_ids is not None and p.department_id not in ctx.scope.department_ids:
            continue
        a = recs.get(p.id)
        out.append({"person_id": str(p.id), "name": p.full_name, "department_id": str(p.department_id) if p.department_id else None,
                    "status": a.status if a else "unmarked", "check_in": a.check_in.isoformat() if a and a.check_in else None,
                    "check_out": a.check_out.isoformat() if a and a.check_out else None})
    return {"day": day.isoformat(), "records": out}
