"""NES Team (employee Android app) API — release 1.

Every endpoint here works on the signed-in employee's own data, or on data the org structure lets
them see (their company/department channels, group news, the staff directory). Manager actions
(leave / field check-in decisions) are checked against the reporting line and the RBAC scope.
"""
from __future__ import annotations

import math
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .. import models as m
from ..ai.runtime import get_setting, operational_status, run_agent
from ..config import settings
from ..db import get_db
from ..deps import Ctx, audit, client_ip, current_ctx
from ..intelligence import OPEN
from ..permissions import can
from ..security import create_file_token, create_token, decrypt_secret, encrypt_secret
from ..util import get_or_404, row
from .auth import LoginIn, authenticate
from .system import DAILY_OPS_DEFAULT

router = APIRouter(prefix="/mobile", tags=["employee-app"])

APP_MIN_VERSION = "1.0.0"
LEAVE_KINDS = {"annual": "Annual leave", "casual": "Casual leave", "sick": "Sick leave",
               "unpaid": "Unpaid leave", "overtime": "Overtime"}
LEAVE_POLICY_DEFAULT = {"annual": 14, "casual": 10, "sick": 8}
ATTENDANCE_POLICY_DEFAULT = {"require_biometric": True, "late_grace_minutes": 15, "max_gps_accuracy_m": 200,
                             "allow_web_checkin_with_sites": False}
HELP_DESK_CODE = "NES-GROUP-HR-EMPLOYEE-HELP-DESK"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return datetime.now(settings.tz).date()


def me_person(ctx: Ctx) -> m.Person:
    p = ctx.db.get(m.Person, ctx.user.person_id) if ctx.user.person_id else None
    if not p:
        raise HTTPException(400, "Your login is not linked to a staff profile. Ask HR to link it.")
    return p


# ================================================================ sign-in & device
class MobileLoginIn(LoginIn):
    device_name: str | None = Field(default=None, max_length=200)
    platform: str | None = Field(default=None, max_length=40)
    app_version: str | None = Field(default=None, max_length=20)
    install_id: str | None = Field(default=None, max_length=64)


@router.get("/config")
def config():
    """Public: lets the app confirm it's talking to an NES GLOBAL OS server during setup."""
    return {"system": "NES GLOBAL OS", "min_app_version": APP_MIN_VERSION, "timezone": settings.timezone,
            "server_time": _now().isoformat()}


@router.post("/login")
def mobile_login(body: MobileLoginIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    user = authenticate(db, body, ip)
    dev = None
    if body.install_id:  # same phone signing in again → reuse its entry
        dev = db.scalar(select(m.Device).where(m.Device.user_id == user.id, m.Device.install_id == body.install_id))
    if dev:
        dev.revoked_at, dev.wipe = None, False
        dev.name, dev.platform, dev.app_version = body.device_name, body.platform, body.app_version
        dev.last_seen_at, dev.last_ip = _now(), ip
    else:
        dev = m.Device(user_id=user.id, install_id=body.install_id, name=body.device_name, platform=body.platform,
                       app_version=body.app_version, last_seen_at=_now(), last_ip=ip)
        db.add(dev)
    db.flush()
    audit(db, "device.register", "device", dev.id, None, {"name": body.device_name}, user_id=user.id,
          label=user.email, ip=ip)
    db.commit()
    person = db.get(m.Person, user.person_id) if user.person_id else None
    return {"token": create_token(user.id, user.role, user.token_version, device_id=dev.id),
            "device_id": str(dev.id), "role": user.role,
            "name": person.full_name if person else user.email}


@router.post("/logout")
def mobile_logout(ctx: Ctx = Depends(current_ctx)):
    if ctx.device:
        ctx.device.revoked_at = _now()
        ctx.audit("device.logout", "device", ctx.device.id)
        ctx.db.commit()
    return {"ok": True}


def _leader(ctx: Ctx) -> bool:
    return ctx.role in {"ceo", "director", "dept_head", "manager"}


# ================================================================ home & sync
def _pending_approvals(ctx: Ctx) -> int:
    n = len(_leave_to_decide(ctx)) + len(_field_to_decide(ctx))
    if can(ctx.role, "approvals.decide"):
        q = select(m.Approval).where(m.Approval.status == "pending")
        n += sum(1 for a in ctx.db.scalars(q) if not a.company_id or ctx.scope.allows_company(a.company_id))
    return n


@router.get("/home")
def home(ctx: Ctx = Depends(current_ctx)):
    db, p = ctx.db, me_person(ctx)
    today = _today()
    att = db.scalar(select(m.Attendance).where(m.Attendance.person_id == p.id, m.Attendance.day == today))
    tasks = list(db.scalars(select(m.Task).where(m.Task.assignee_person_id == p.id, m.Task.status.in_(OPEN))
                            .order_by(m.Task.due_at.nulls_last()).limit(5)))
    open_count = db.scalar(select(func.count()).where(m.Task.assignee_person_id == p.id, m.Task.status.in_(OPEN)))
    news = _visible_news(ctx, limit=3)
    company = db.get(m.Company, p.company_id) if p.company_id else None
    dept = db.get(m.Department, p.department_id) if p.department_id else None
    return {
        "person": {"id": str(p.id), "name": p.full_name, "designation": p.designation, "code": p.employee_code,
                   "company": company.name if company else None, "department": dept.name if dept else None},
        "role": ctx.role, "is_leader": _leader(ctx), "today": today.isoformat(),
        "working_day": today.weekday() in _ops(db)["workdays"],
        "attendance": _att_view(att), "shift": _shift_for(db, p, today),
        "leave_balances": _balances(db, p, today.year),
        "tasks": {"open": open_count, "next": [{"id": str(t.id), "title": t.title, "status": t.status,
                                               "due_at": t.due_at.isoformat() if t.due_at else None,
                                               "overdue": bool(t.due_at and t.due_at < _now())} for t in tasks]},
        "news": news, "unread_news": _unread_news(ctx), "unread_chat": _unread_chat_total(ctx),
        "pending_approvals": _pending_approvals(ctx) if _leader(ctx) else 0,
        "missed_calls": _missed(ctx),
    }


def _missed(ctx: Ctx) -> int:
    from .calls import missed_unseen
    return missed_unseen(ctx.db, ctx.user.id)


@router.get("/sync")
def sync(since: datetime | None = None, ctx: Ctx = Depends(current_ctx)):
    """Polled by the app every ~30 s while open: counts + anything new to notify about."""
    since = since or (_now() - timedelta(minutes=5))
    urgent = [n for n in _visible_news(ctx, limit=10) if n["priority"] == "urgent" and not n["read"]
              and n["created_at"] > since.isoformat()]
    return {"server_time": _now().isoformat(), "unread_chat": _unread_chat_total(ctx),
            "unread_news": _unread_news(ctx), "new_urgent": urgent, "missed_calls": _missed(ctx),
            "pending_approvals": _pending_approvals(ctx) if _leader(ctx) else 0}


# ================================================================ attendance (geofence + biometric)
def _ops(db) -> dict:
    return get_setting(db, "daily_ops", DAILY_OPS_DEFAULT)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_site(db, person: m.Person, lat: float, lng: float):
    sites = [s for s in db.scalars(select(m.WorkSite).where(m.WorkSite.active.is_(True)))
             if s.company_id is None or s.company_id == person.company_id]
    best = None
    for s in sites:
        d = haversine_m(lat, lng, float(s.lat), float(s.lng))
        if best is None or d < best[1]:
            best = (s, d)
    return sites, best


def _att_view(a: m.Attendance | None) -> dict | None:
    if not a:
        return None
    return {"id": str(a.id), "day": a.day.isoformat(), "status": a.status, "method": a.method,
            "check_in": a.check_in.isoformat() if a.check_in else None,
            "check_out": a.check_out.isoformat() if a.check_out else None,
            "outside_geofence": a.outside_geofence, "field_approved": a.field_approved,
            "distance_m": float(a.in_distance_m) if a.in_distance_m is not None else None, "note": a.note}


def _shift_for(db, person: m.Person, day: date) -> dict:
    s = db.scalar(select(m.Shift).where(m.Shift.person_id == person.id, m.Shift.day == day))
    if s:
        site = db.get(m.WorkSite, s.site_id) if s.site_id else None
        return {"day": day.isoformat(), "start": s.start_time, "end": s.end_time, "site": site.name if site else None,
                "note": s.note, "custom": True, "off": False}
    ops = _ops(db)
    off = day.weekday() not in ops["workdays"]
    return {"day": day.isoformat(), "start": None if off else ops["office_start"], "end": None if off else ops["office_end"],
            "site": None, "note": "Day off" if off else "Standard office hours", "custom": False, "off": off}


class CheckInIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(ge=0, le=100000)
    biometric_confirmed: bool = False
    field_note: str | None = Field(default=None, max_length=500)  # required when outside every geofence


@router.post("/attendance/check-in")
def check_in(body: CheckInIn, ctx: Ctx = Depends(current_ctx)):
    db, p = ctx.db, me_person(ctx)
    pol = get_setting(db, "attendance_policy", ATTENDANCE_POLICY_DEFAULT)
    if pol["require_biometric"] and not body.biometric_confirmed:
        raise HTTPException(400, "Confirm with your fingerprint or face to check in.")
    if body.accuracy_m > pol["max_gps_accuracy_m"]:
        raise HTTPException(400, f"GPS signal is weak (±{int(body.accuracy_m)} m). Turn on location, move near a "
                                 "window or outside, and try again.")
    today = _today()
    rec = db.scalar(select(m.Attendance).where(m.Attendance.person_id == p.id, m.Attendance.day == today))
    if rec and rec.check_in:
        raise HTTPException(409, "You have already checked in today.")
    sites, best = nearest_site(db, p, body.lat, body.lng)
    inside = False
    if best:
        site, dist = best
        inside = dist <= site.radius_m + min(body.accuracy_m, 100)
    if sites and not inside and not (body.field_note and body.field_note.strip()):
        name, dist = (best[0].name, round(best[1])) if best else ("office", 0)
        raise HTTPException(422, detail={"outside_geofence": True, "nearest_site": name, "distance_m": dist,
                                         "message": f"You are {dist} m from {name}. If you're at a client site or on "
                                                    "field work, add a short note to check in for manager review."})
    now_local = datetime.now(settings.tz)
    shift = _shift_for(db, p, today)
    start = shift["start"] or _ops(db)["office_start"]
    late_after = datetime.combine(today, time.fromisoformat(start), tzinfo=settings.tz) + \
        timedelta(minutes=int(pol["late_grace_minutes"]))
    if not rec:
        rec = m.Attendance(person_id=p.id, day=today)
        db.add(rec)
    rec.check_in, rec.method, rec.device_id = _now(), "mobile", ctx.device.id if ctx.device else None
    rec.in_lat, rec.in_lng, rec.in_accuracy_m = body.lat, body.lng, body.accuracy_m
    rec.biometric_confirmed = body.biometric_confirmed
    rec.site_id = best[0].id if best else None
    rec.in_distance_m = round(best[1], 1) if best else None
    if sites and not inside:
        rec.status, rec.outside_geofence, rec.field_approved, rec.note = "remote", True, None, body.field_note.strip()
    else:
        rec.status = "late" if now_local > late_after else "present"
        rec.outside_geofence = False
    ctx.audit("attendance.check_in", "person", p.id, p.company_id, status=rec.status, method="mobile",
              site=best[0].name if best else None, distance_m=rec.in_distance_m, outside=rec.outside_geofence)
    db.commit()
    return {"attendance": _att_view(rec), "site": best[0].name if best else None,
            "geofence_configured": bool(sites)}


class CheckOutIn(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


@router.post("/attendance/check-out")
def check_out(body: CheckOutIn, ctx: Ctx = Depends(current_ctx)):
    p = me_person(ctx)
    rec = ctx.db.scalar(select(m.Attendance).where(m.Attendance.person_id == p.id, m.Attendance.day == _today()))
    if not rec or not rec.check_in:
        raise HTTPException(400, "You have not checked in today.")
    if rec.check_out:
        raise HTTPException(409, "You have already checked out today.")
    rec.check_out, rec.out_lat, rec.out_lng = _now(), body.lat, body.lng
    ctx.audit("attendance.check_out", "person", p.id, p.company_id)
    ctx.db.commit()
    return {"attendance": _att_view(rec)}


@router.get("/attendance/history")
def attendance_history(month: str | None = None, ctx: Ctx = Depends(current_ctx)):
    p = me_person(ctx)
    first = date.fromisoformat((month or _today().strftime("%Y-%m")) + "-01")
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    recs = list(ctx.db.scalars(select(m.Attendance).where(m.Attendance.person_id == p.id, m.Attendance.day >= first,
                                                           m.Attendance.day < nxt).order_by(m.Attendance.day.desc())))
    summary: dict[str, int] = {}
    for r in recs:
        summary[r.status] = summary.get(r.status, 0) + 1
    return {"month": first.strftime("%Y-%m"), "summary": summary, "records": [_att_view(r) for r in recs]}


# ================================================================ leave & overtime
def working_days(db, start: date, end: date) -> int:
    wd = _ops(db)["workdays"]
    return sum(1 for i in range((end - start).days + 1) if (start + timedelta(days=i)).weekday() in wd)


def _balances(db, p: m.Person, year: int) -> list[dict]:
    pol = get_setting(db, "leave_policy", LEAVE_POLICY_DEFAULT)
    used = dict(db.execute(select(m.LeaveRequest.kind, func.coalesce(func.sum(m.LeaveRequest.days), 0))
                           .where(m.LeaveRequest.person_id == p.id, m.LeaveRequest.status == "approved",
                                  func.extract("year", m.LeaveRequest.start_on) == year)
                           .group_by(m.LeaveRequest.kind)).all())
    pending = dict(db.execute(select(m.LeaveRequest.kind, func.coalesce(func.sum(m.LeaveRequest.days), 0))
                              .where(m.LeaveRequest.person_id == p.id, m.LeaveRequest.status == "pending",
                                     func.extract("year", m.LeaveRequest.start_on) == year)
                              .group_by(m.LeaveRequest.kind)).all())
    out = []
    for k, ent in pol.items():
        u, pe = float(used.get(k, 0)), float(pending.get(k, 0))
        out.append({"kind": k, "label": LEAVE_KINDS.get(k, k), "entitled": float(ent), "used": u, "pending": pe,
                    "remaining": float(ent) - u})
    return out


def _approver_for(db, p: m.Person) -> uuid.UUID | None:
    if p.manager_id and p.manager_id != p.id:
        return p.manager_id
    if p.department_id:
        d = db.get(m.Department, p.department_id)
        if d and d.head_person_id and d.head_person_id != p.id:
            return d.head_person_id
    ceo = db.scalar(select(m.User).where(m.User.role == "ceo"))
    return ceo.person_id if ceo else None


def _leave_view(db, lr: m.LeaveRequest, with_person=False) -> dict:
    d = row(lr, label=LEAVE_KINDS.get(lr.kind, lr.kind))
    if with_person:
        p = db.get(m.Person, lr.person_id)
        d["person"] = {"id": str(p.id), "name": p.full_name, "designation": p.designation} if p else None
    return d


@router.get("/leave")
def my_leave(ctx: Ctx = Depends(current_ctx)):
    p = me_person(ctx)
    reqs = list(ctx.db.scalars(select(m.LeaveRequest).where(m.LeaveRequest.person_id == p.id)
                               .order_by(m.LeaveRequest.start_on.desc()).limit(50)))
    return {"kinds": LEAVE_KINDS, "balances": _balances(ctx.db, p, _today().year),
            "requests": [_leave_view(ctx.db, r) for r in reqs]}


class LeaveIn(BaseModel):
    kind: str
    start_on: date
    end_on: date
    half_day: bool = False
    hours: Decimal | None = Field(default=None, gt=0, le=24)
    reason: str | None = Field(default=None, max_length=1000)


@router.post("/leave", status_code=201)
def apply_leave(body: LeaveIn, ctx: Ctx = Depends(current_ctx)):
    db, p = ctx.db, me_person(ctx)
    if body.kind not in LEAVE_KINDS:
        raise HTTPException(400, "Unknown leave type")
    if body.end_on < body.start_on:
        raise HTTPException(400, "End date is before start date")
    if body.start_on < _today() - timedelta(days=30):
        raise HTTPException(400, "Requests older than 30 days need HR")
    if (body.end_on - body.start_on).days > 90:
        raise HTTPException(400, "A single request can cover at most 90 days")
    if body.kind == "overtime":
        if not body.hours or body.start_on != body.end_on:
            raise HTTPException(400, "Overtime needs one date and the number of hours")
        days = Decimal(0)
    else:
        if body.half_day and body.start_on != body.end_on:
            raise HTTPException(400, "Half day is only for a single date")
        n = working_days(db, body.start_on, body.end_on)
        if n == 0:
            raise HTTPException(400, "Those dates are not working days")
        days = Decimal("0.5") if body.half_day else Decimal(n)
        overlap = db.scalar(select(m.LeaveRequest).where(
            m.LeaveRequest.person_id == p.id, m.LeaveRequest.kind != "overtime",
            m.LeaveRequest.status.in_(["pending", "approved"]),
            m.LeaveRequest.start_on <= body.end_on, m.LeaveRequest.end_on >= body.start_on))
        if overlap:
            raise HTTPException(409, f"You already have a {overlap.status} request covering "
                                     f"{overlap.start_on:%d %b}–{overlap.end_on:%d %b}.")
        bal = next((b for b in _balances(db, p, body.start_on.year) if b["kind"] == body.kind), None)
        if bal and float(days) > bal["remaining"] - bal["pending"]:
            raise HTTPException(400, f"Not enough {bal['label'].lower()}: {bal['remaining'] - bal['pending']:g} "
                                     f"day(s) available, {float(days):g} requested.")
    lr = m.LeaveRequest(person_id=p.id, kind=body.kind, start_on=body.start_on, end_on=body.end_on,
                        half_day=body.half_day, days=days, hours=body.hours, reason=body.reason,
                        approver_person_id=_approver_for(db, p))
    db.add(lr)
    db.flush()
    ctx.audit("leave.request", "leave", lr.id, p.company_id, kind=lr.kind, days=str(days))
    db.commit()
    return _leave_view(db, lr)


@router.post("/leave/{lid}/cancel")
def cancel_leave(lid: str, ctx: Ctx = Depends(current_ctx)):
    lr = get_or_404(ctx.db, m.LeaveRequest, lid, "Request")
    if lr.person_id != ctx.user.person_id:
        raise HTTPException(403, "Not your request")
    if lr.status != "pending":
        raise HTTPException(409, f"Request is already {lr.status}")
    lr.status = "cancelled"
    ctx.audit("leave.cancel", "leave", lr.id, None)
    ctx.db.commit()
    return _leave_view(ctx.db, lr)


def can_manage_person(ctx: Ctx, person: m.Person) -> bool:
    if person.id == ctx.user.person_id and ctx.role != "ceo":
        return False
    if ctx.role == "ceo":
        return True
    if person.manager_id and person.manager_id == ctx.user.person_id:
        return True
    if ctx.role == "director":
        return ctx.scope.allows_company(person.company_id)
    if ctx.role in {"dept_head", "manager"}:
        return ctx.scope.department_ids is not None and person.department_id in ctx.scope.department_ids
    return False


def _leave_to_decide(ctx: Ctx) -> list[m.LeaveRequest]:
    if not _leader(ctx):
        q = select(m.LeaveRequest).where(m.LeaveRequest.status == "pending",
                                         m.LeaveRequest.approver_person_id == ctx.user.person_id)
    else:
        q = select(m.LeaveRequest).where(m.LeaveRequest.status == "pending")
    out = []
    for lr in ctx.db.scalars(q.order_by(m.LeaveRequest.start_on)):
        p = ctx.db.get(m.Person, lr.person_id)
        if p and (lr.approver_person_id == ctx.user.person_id and p.id != ctx.user.person_id or can_manage_person(ctx, p)):
            out.append(lr)
    return out


def _field_to_decide(ctx: Ctx) -> list[m.Attendance]:
    if not _leader(ctx):
        return []
    since = _today() - timedelta(days=14)
    out = []
    for a in ctx.db.scalars(select(m.Attendance).where(m.Attendance.outside_geofence.is_(True),
                                                       m.Attendance.field_approved.is_(None), m.Attendance.day >= since)):
        p = ctx.db.get(m.Person, a.person_id)
        if p and can_manage_person(ctx, p):
            out.append(a)
    return out


@router.get("/approvals")
def approvals(ctx: Ctx = Depends(current_ctx)):
    db = ctx.db
    leave = [_leave_view(db, lr, with_person=True) for lr in _leave_to_decide(ctx)]
    field = []
    for a in _field_to_decide(ctx):
        p = db.get(m.Person, a.person_id)
        site = db.get(m.WorkSite, a.site_id) if a.site_id else None
        field.append({**_att_view(a), "person": {"id": str(p.id), "name": p.full_name},
                      "nearest_site": site.name if site else None,
                      "map": f"https://maps.google.com/?q={a.in_lat},{a.in_lng}" if a.in_lat is not None else None})
    system = []
    if can(ctx.role, "approvals.decide"):
        for a in db.scalars(select(m.Approval).where(m.Approval.status == "pending").order_by(m.Approval.created_at.desc())):
            if a.company_id and not ctx.scope.allows_company(a.company_id):
                continue
            agent = db.get(m.Agent, a.requested_by_agent_id) if a.requested_by_agent_id else None
            system.append({"id": str(a.id), "kind": a.kind, "title": a.title, "created_at": a.created_at.isoformat(),
                           "requested_by": agent.name if agent else None,
                           "summary": (a.payload or {}).get("request", {}).get("summary")})
    return {"leave": leave, "field_checkins": field, "system": system}


class DecideIn(BaseModel):
    decision: str
    note: str | None = Field(default=None, max_length=500)


@router.post("/leave/{lid}/decide")
def decide_leave(lid: str, body: DecideIn, ctx: Ctx = Depends(current_ctx)):
    db = ctx.db
    lr = get_or_404(db, m.LeaveRequest, lid, "Request")
    p = db.get(m.Person, lr.person_id)
    allowed = (lr.approver_person_id == ctx.user.person_id and p.id != ctx.user.person_id) or can_manage_person(ctx, p)
    if not allowed:
        raise HTTPException(403, "You can't decide this request")
    if lr.status != "pending":
        raise HTTPException(409, f"Already {lr.status}")
    if body.decision not in {"approved", "rejected"}:
        raise HTTPException(400, "Decision must be approved or rejected")
    lr.status, lr.decided_by_user_id, lr.decided_at, lr.decision_note = body.decision, ctx.user.id, _now(), body.note
    if body.decision == "approved" and lr.kind != "overtime":
        wd = _ops(db)["workdays"]
        for i in range((lr.end_on - lr.start_on).days + 1):
            d = lr.start_on + timedelta(days=i)
            if d.weekday() not in wd:
                continue
            a = db.scalar(select(m.Attendance).where(m.Attendance.person_id == p.id, m.Attendance.day == d))
            if not a:
                a = m.Attendance(person_id=p.id, day=d)
                db.add(a)
            if not a.check_in:
                a.status, a.method, a.note = "leave", "manual", f"{LEAVE_KINDS[lr.kind]} (approved)"
    ctx.audit(f"leave.{body.decision}", "leave", lr.id, p.company_id, person=p.full_name, kind=lr.kind)
    db.commit()
    return _leave_view(db, lr, with_person=True)


@router.post("/attendance/{aid}/field-decide")
def decide_field(aid: str, body: DecideIn, ctx: Ctx = Depends(current_ctx)):
    a = get_or_404(ctx.db, m.Attendance, aid, "Attendance")
    p = ctx.db.get(m.Person, a.person_id)
    if not can_manage_person(ctx, p):
        raise HTTPException(403, "You can't review this check-in")
    if not a.outside_geofence or a.field_approved is not None:
        raise HTTPException(409, "Nothing to review")
    if body.decision not in {"approved", "rejected"}:
        raise HTTPException(400, "Decision must be approved or rejected")
    a.field_approved = body.decision == "approved"
    if not a.field_approved:
        a.status = "absent"
        a.note = (a.note or "") + f" | Rejected: {body.note or 'no reason given'}"
    ctx.audit(f"attendance.field_{body.decision}", "person", p.id, p.company_id, day=str(a.day))
    ctx.db.commit()
    return _att_view(a)


# ================================================================ shifts
@router.get("/shifts")
def my_shifts(days: int = 7, ctx: Ctx = Depends(current_ctx)):
    p = me_person(ctx)
    start = _today()
    return [_shift_for(ctx.db, p, start + timedelta(days=i)) for i in range(max(1, min(days, 31)))]


@router.get("/shifts/team")
def team_shifts(day: date | None = None, ctx: Ctx = Depends(current_ctx)):
    if not _leader(ctx):
        raise HTTPException(403, "Managers only")
    day = day or _today()
    out = []
    for p in ctx.db.scalars(select(m.Person).where(m.Person.status != "inactive").order_by(m.Person.full_name)):
        if p.id != ctx.user.person_id and not can_manage_person(ctx, p):
            continue
        a = ctx.db.scalar(select(m.Attendance).where(m.Attendance.person_id == p.id, m.Attendance.day == day))
        out.append({"person": {"id": str(p.id), "name": p.full_name, "designation": p.designation},
                    "shift": _shift_for(ctx.db, p, day), "attendance": _att_view(a)})
    return {"day": day.isoformat(), "team": out}


class ShiftIn(BaseModel):
    person_id: uuid.UUID
    day: date
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    site_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=200)


@router.put("/shifts")
def set_shift(body: ShiftIn, ctx: Ctx = Depends(current_ctx)):
    p = get_or_404(ctx.db, m.Person, body.person_id, "Person")
    if not _leader(ctx) or not (can_manage_person(ctx, p) or p.id == ctx.user.person_id and ctx.role == "ceo"):
        raise HTTPException(403, "You can't set shifts for this person")
    s = ctx.db.scalar(select(m.Shift).where(m.Shift.person_id == p.id, m.Shift.day == body.day))
    if not s:
        s = m.Shift(person_id=p.id, day=body.day, start_time=body.start_time, end_time=body.end_time)
        ctx.db.add(s)
    s.start_time, s.end_time, s.site_id, s.note = body.start_time, body.end_time, body.site_id, body.note
    ctx.audit("shift.set", "person", p.id, p.company_id, day=str(body.day))
    ctx.db.commit()
    return row(s)


@router.delete("/shifts/{person_id}/{day}")
def clear_shift(person_id: uuid.UUID, day: date, ctx: Ctx = Depends(current_ctx)):
    p = get_or_404(ctx.db, m.Person, person_id, "Person")
    if not _leader(ctx) or not can_manage_person(ctx, p):
        raise HTTPException(403, "Not allowed")
    s = ctx.db.scalar(select(m.Shift).where(m.Shift.person_id == p.id, m.Shift.day == day))
    if s:
        ctx.db.delete(s)
        ctx.db.commit()
    return {"ok": True}


# ================================================================ directory
@router.get("/directory")
def directory(q: str | None = None, ctx: Ctx = Depends(current_ctx)):
    db = ctx.db
    comps = {c.id: c.name for c in db.scalars(select(m.Company))}
    depts = {d.id: d.name for d in db.scalars(select(m.Department))}
    users = {u.person_id: u for u in db.scalars(select(m.User).where(m.User.person_id.is_not(None), m.User.is_active.is_(True)))}
    from ..realtime import online_ids_sync
    online = online_ids_sync()
    out = []
    for p in db.scalars(select(m.Person).where(m.Person.status != "inactive").order_by(m.Person.full_name)):
        item = {"id": str(p.id), "name": p.full_name, "designation": p.designation,
                "company": comps.get(p.company_id), "department": depts.get(p.department_id),
                "phone": p.phone, "email": p.email, "code": p.employee_code,
                "user_id": str(users[p.id].id) if p.id in users else None,
                "online": p.id in users and str(users[p.id].id) in online,
                "manager_id": str(p.manager_id) if p.manager_id else None}
        hay = " ".join(str(v or "") for v in (p.full_name, p.designation, item["company"], item["department"],
                                               p.phone, p.email, " ".join(p.skills or []))).lower()
        if not q or q.lower() in hay:
            out.append(item)
    return out


# ================================================================ news
def _news_visible_to(person: m.Person | None, n: m.Announcement) -> bool:
    if n.company_id is None and n.department_id is None:
        return True
    if not person:
        return False
    if n.department_id:
        return n.department_id == person.department_id
    return n.company_id == person.company_id


def _visible_news(ctx: Ctx, limit: int = 50) -> list[dict]:
    db = ctx.db
    person = db.get(m.Person, ctx.user.person_id) if ctx.user.person_id else None
    reads = set(db.scalars(select(m.AnnouncementRead.announcement_id).where(m.AnnouncementRead.user_id == ctx.user.id)))
    out = []
    for n in db.scalars(select(m.Announcement).order_by(m.Announcement.pinned.desc(), m.Announcement.created_at.desc()).limit(300)):
        if ctx.role == "ceo" or _news_visible_to(person, n):
            author = db.get(m.User, n.author_user_id) if n.author_user_id else None
            ap = db.get(m.Person, author.person_id) if author and author.person_id else None
            out.append({"id": str(n.id), "title": n.title, "body": n.body, "priority": n.priority, "pinned": n.pinned,
                        "created_at": n.created_at.isoformat(), "read": n.id in reads,
                        "author": ap.full_name if ap else (author.email if author else None),
                        "audience": "Whole group" if not n.company_id and not n.department_id else
                        (db.get(m.Department, n.department_id).name if n.department_id else db.get(m.Company, n.company_id).name)})
            if len(out) >= limit:
                break
    return out


def _unread_news(ctx: Ctx) -> int:
    return sum(1 for n in _visible_news(ctx, limit=200) if not n["read"])


@router.get("/news")
def news(ctx: Ctx = Depends(current_ctx)):
    return _visible_news(ctx)


@router.post("/news/{nid}/read")
def read_news(nid: str, ctx: Ctx = Depends(current_ctx)):
    n = get_or_404(ctx.db, m.Announcement, nid, "Announcement")
    if not ctx.db.get(m.AnnouncementRead, (n.id, ctx.user.id)):
        ctx.db.add(m.AnnouncementRead(announcement_id=n.id, user_id=ctx.user.id))
        ctx.db.commit()
    return {"ok": True}


class NewsIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    priority: str = "normal"
    pinned: bool = False
    company_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None


@router.post("/news", status_code=201)
def post_news(body: NewsIn, ctx: Ctx = Depends(current_ctx)):
    if ctx.role not in {"ceo", "director", "dept_head"}:
        raise HTTPException(403, "Only the CEO, directors and department heads can post announcements")
    if body.priority not in {"normal", "urgent"}:
        raise HTTPException(400, "Priority must be normal or urgent")
    if ctx.role != "ceo":
        if body.department_id:
            d = get_or_404(ctx.db, m.Department, body.department_id, "Department")
            if not ctx.scope.allows_company(d.company_id) or (ctx.scope.department_ids is not None and d.id not in ctx.scope.department_ids):
                raise HTTPException(403, "That department is outside your access")
            body.company_id = d.company_id
        elif body.company_id:
            if ctx.role == "dept_head" or not ctx.scope.allows_company(body.company_id):
                raise HTTPException(403, "That company is outside your access")
        else:
            raise HTTPException(403, "Only the CEO can post to the whole group")
    n = m.Announcement(**body.model_dump(), author_user_id=ctx.user.id)
    ctx.db.add(n)
    ctx.db.flush()
    ctx.audit("news.post", "announcement", n.id, n.company_id, title=n.title, priority=n.priority)
    ctx.db.commit()
    return row(n)


@router.delete("/news/{nid}")
def delete_news(nid: str, ctx: Ctx = Depends(current_ctx)):
    n = get_or_404(ctx.db, m.Announcement, nid, "Announcement")
    if not (ctx.role == "ceo" or n.author_user_id == ctx.user.id):
        raise HTTPException(403, "Only the author or the CEO can remove this")
    ctx.audit("news.delete", "announcement", n.id, n.company_id, title=n.title)
    ctx.db.delete(n)
    ctx.db.commit()
    return {"ok": True}


# ================================================================ chat
def _ensure_default_channels(ctx: Ctx) -> None:
    db = ctx.db
    person = db.get(m.Person, ctx.user.person_id) if ctx.user.person_id else None
    wanted = [("all", "all", "All NES staff", None, None)]
    if person and person.company_id:
        c = db.get(m.Company, person.company_id)
        wanted.append((f"co:{c.id}", "company", c.name, c.id, None))
    if person and person.department_id:
        d = db.get(m.Department, person.department_id)
        wanted.append((f"dept:{d.id}", "department", d.name, d.company_id, d.id))
    created = False
    for key, kind, name, cid, did in wanted:
        if not db.scalar(select(m.ChatChannel.id).where(m.ChatChannel.direct_key == key)):
            db.add(m.ChatChannel(kind=kind, name=name, company_id=cid, department_id=did, direct_key=key))
            created = True
    if created:
        db.commit()


def can_access_channel(ctx: Ctx, ch: m.ChatChannel) -> bool:
    if ch.kind == "all":
        return True
    person = ctx.db.get(m.Person, ctx.user.person_id) if ctx.user.person_id else None
    if ch.kind == "company":
        return bool(person and person.company_id == ch.company_id)
    if ch.kind == "department":
        return bool(person and person.department_id == ch.department_id)
    return ctx.db.get(m.ChatMember, (ch.id, ctx.user.id)) is not None


def _my_channels(ctx: Ctx) -> list[m.ChatChannel]:
    _ensure_default_channels(ctx)
    db = ctx.db
    person = db.get(m.Person, ctx.user.person_id) if ctx.user.person_id else None
    conds = [m.ChatChannel.kind == "all",
             m.ChatChannel.id.in_(select(m.ChatMember.channel_id).where(m.ChatMember.user_id == ctx.user.id))]
    if person and person.company_id:
        conds.append(and_(m.ChatChannel.kind == "company", m.ChatChannel.company_id == person.company_id))
    if person and person.department_id:
        conds.append(and_(m.ChatChannel.kind == "department", m.ChatChannel.department_id == person.department_id))
    return list(db.scalars(select(m.ChatChannel).where(or_(*conds))))


def _unread(ctx: Ctx, ch: m.ChatChannel) -> int:
    r = ctx.db.get(m.ChatRead, (ch.id, ctx.user.id))
    q = select(func.count()).where(m.ChatMessage.channel_id == ch.id, m.ChatMessage.deleted.is_(False),
                                   or_(m.ChatMessage.sender_user_id.is_(None), m.ChatMessage.sender_user_id != ctx.user.id))
    if r:
        q = q.where(m.ChatMessage.created_at > r.last_read_at)
    return ctx.db.scalar(q) or 0


def _unread_chat_total(ctx: Ctx) -> int:
    return sum(_unread(ctx, ch) for ch in _my_channels(ctx))


def _user_name(db, uid) -> str:
    u = db.get(m.User, uid) if uid else None
    if not u:
        return "System"
    p = db.get(m.Person, u.person_id) if u.person_id else None
    return p.full_name if p else u.email


def _msg_view(db, msg: m.ChatMessage, me: uuid.UUID) -> dict:
    return {"id": str(msg.id), "body": "(message deleted)" if msg.deleted else (decrypt_secret(msg.body_enc) or ""),
            "sender_user_id": str(msg.sender_user_id) if msg.sender_user_id else None,
            "sender": _user_name(db, msg.sender_user_id), "mine": msg.sender_user_id == me,
            "created_at": msg.created_at.isoformat(), "deleted": msg.deleted}


def _channel_title(ctx: Ctx, ch: m.ChatChannel) -> str:
    if ch.kind != "direct":
        return ch.name or "Group"
    other = ctx.db.scalar(select(m.ChatMember.user_id).where(m.ChatMember.channel_id == ch.id, m.ChatMember.user_id != ctx.user.id))
    return _user_name(ctx.db, other) if other else "Notes to self"


@router.get("/chat/channels")
def channels(ctx: Ctx = Depends(current_ctx)):
    db = ctx.db
    out = []
    for ch in _my_channels(ctx):
        last = db.scalar(select(m.ChatMessage).where(m.ChatMessage.channel_id == ch.id)
                         .order_by(m.ChatMessage.created_at.desc()).limit(1))
        out.append({"id": str(ch.id), "kind": ch.kind, "title": _channel_title(ctx, ch), "unread": _unread(ctx, ch),
                    "last": _msg_view(db, last, ctx.user.id) if last else None,
                    "sort": (last.created_at if last else ch.created_at).isoformat()})
    order = {"all": 0, "company": 1, "department": 2}
    out.sort(key=lambda c: (c["kind"] not in order, order.get(c["kind"], 3), c["sort"]), reverse=False)
    fixed = [c for c in out if c["kind"] in order]
    rest = sorted([c for c in out if c["kind"] not in order], key=lambda c: c["sort"], reverse=True)
    return fixed + rest


class DirectIn(BaseModel):
    user_id: uuid.UUID


@router.post("/chat/direct")
def open_direct(body: DirectIn, ctx: Ctx = Depends(current_ctx)):
    other = ctx.db.get(m.User, body.user_id)
    if not other or not other.is_active:
        raise HTTPException(404, "That colleague doesn't have an active login")
    key = "dm:" + ":".join(sorted([str(ctx.user.id), str(other.id)]))
    ch = ctx.db.scalar(select(m.ChatChannel).where(m.ChatChannel.direct_key == key))
    if not ch:
        ch = m.ChatChannel(kind="direct", direct_key=key, created_by_user_id=ctx.user.id)
        ctx.db.add(ch)
        ctx.db.flush()
        for uid in {ctx.user.id, other.id}:
            ctx.db.add(m.ChatMember(channel_id=ch.id, user_id=uid))
        ctx.db.commit()
    return {"id": str(ch.id), "kind": ch.kind, "title": _channel_title(ctx, ch)}


@router.get("/chat/{cid}/messages")
def messages(cid: str, after: datetime | None = None, before: datetime | None = None,
             ctx: Ctx = Depends(current_ctx)):
    ch = get_or_404(ctx.db, m.ChatChannel, cid, "Conversation")
    if not can_access_channel(ctx, ch):
        raise HTTPException(403, "You are not in this conversation")
    q = select(m.ChatMessage).where(m.ChatMessage.channel_id == ch.id)
    if after:
        q = q.where(m.ChatMessage.created_at > after).order_by(m.ChatMessage.created_at).limit(200)
        msgs = list(ctx.db.scalars(q))
    else:
        if before:
            q = q.where(m.ChatMessage.created_at < before)
        msgs = list(reversed(list(ctx.db.scalars(q.order_by(m.ChatMessage.created_at.desc()).limit(60)))))
    other = None
    if ch.kind == "direct":
        other = ctx.db.scalar(select(m.ChatMember.user_id).where(m.ChatMember.channel_id == ch.id,
                                                                  m.ChatMember.user_id != ctx.user.id))
    return {"channel": {"id": str(ch.id), "kind": ch.kind, "title": _channel_title(ctx, ch),
                        "other_user_id": str(other) if other else None},
            "messages": [_msg_view(ctx.db, x, ctx.user.id) for x in msgs]}


class MsgIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@router.post("/chat/{cid}/messages", status_code=201)
def send(cid: str, body: MsgIn, ctx: Ctx = Depends(current_ctx)):
    ch = get_or_404(ctx.db, m.ChatChannel, cid, "Conversation")
    if not can_access_channel(ctx, ch):
        raise HTTPException(403, "You are not in this conversation")
    text = body.body.strip()
    if not text:
        raise HTTPException(400, "Empty message")
    msg = m.ChatMessage(channel_id=ch.id, sender_user_id=ctx.user.id, body_enc=encrypt_secret(text))
    ch.last_message_at = _now()
    ctx.db.add(msg)
    _mark_read(ctx, ch)
    ctx.db.commit()
    return _msg_view(ctx.db, msg, ctx.user.id)


def _mark_read(ctx: Ctx, ch: m.ChatChannel) -> None:
    r = ctx.db.get(m.ChatRead, (ch.id, ctx.user.id))
    if r:
        r.last_read_at = _now()
    else:
        ctx.db.add(m.ChatRead(channel_id=ch.id, user_id=ctx.user.id, last_read_at=_now()))


@router.post("/chat/{cid}/read")
def read(cid: str, ctx: Ctx = Depends(current_ctx)):
    ch = get_or_404(ctx.db, m.ChatChannel, cid, "Conversation")
    if not can_access_channel(ctx, ch):
        raise HTTPException(403, "You are not in this conversation")
    _mark_read(ctx, ch)
    ctx.db.commit()
    return {"ok": True}


@router.delete("/chat/messages/{mid}")
def delete_message(mid: str, ctx: Ctx = Depends(current_ctx)):
    msg = get_or_404(ctx.db, m.ChatMessage, mid, "Message")
    if msg.sender_user_id != ctx.user.id:
        raise HTTPException(403, "You can only delete your own messages")
    msg.deleted, msg.body_enc = True, encrypt_secret("")
    ctx.db.commit()
    return {"ok": True}


# ================================================================ documents
def doc_visible(ctx: Ctx, d: m.Document) -> bool:
    if ctx.role == "ceo":
        return True
    if d.person_id:
        return d.person_id == ctx.user.person_id or (_leader(ctx) and _person_manageable(ctx, d.person_id))
    if d.leaders_only and not _leader(ctx):
        return False
    person = ctx.db.get(m.Person, ctx.user.person_id) if ctx.user.person_id else None
    if d.department_id:
        return bool(person and person.department_id == d.department_id) or \
            (ctx.scope.department_ids is None and ctx.scope.allows_company(d.company_id) and _leader(ctx))
    if d.company_id:
        return bool(person and person.company_id == d.company_id) or (ctx.scope.company_ids is None)
    return True


def _person_manageable(ctx: Ctx, pid) -> bool:
    p = ctx.db.get(m.Person, pid)
    return bool(p and can_manage_person(ctx, p))


def _doc_view(d: m.Document, full: bool = False) -> dict:
    v = {"id": str(d.id), "title": d.title, "category": d.category, "has_file": bool(d.file_path),
         "file_name": d.file_name, "mime": d.mime, "size_bytes": d.size_bytes, "version": d.version,
         "updated_at": d.updated_at.isoformat(), "personal": bool(d.person_id), "leaders_only": d.leaders_only,
         "company_id": str(d.company_id) if d.company_id else None,
         "department_id": str(d.department_id) if d.department_id else None,
         "excerpt": (d.body_text or "")[:220]}
    if full:
        v["body_text"] = d.body_text
    return v


@router.get("/documents")
def documents(q: str | None = None, category: str | None = None, ctx: Ctx = Depends(current_ctx)):
    query = select(m.Document).order_by(m.Document.category, m.Document.title)
    if category:
        query = query.where(m.Document.category == category)
    out = []
    for d in ctx.db.scalars(query):
        if not doc_visible(ctx, d):
            continue
        if q and q.lower() not in f"{d.title} {d.body_text or ''}".lower():
            continue
        out.append(_doc_view(d))
    return out


@router.get("/documents/{did}")
def document(did: str, ctx: Ctx = Depends(current_ctx)):
    d = get_or_404(ctx.db, m.Document, did, "Document")
    if not doc_visible(ctx, d):
        raise HTTPException(403, "You don't have access to this document")
    return _doc_view(d, full=True)


@router.post("/documents/{did}/link")
def document_link(did: str, ctx: Ctx = Depends(current_ctx)):
    d = get_or_404(ctx.db, m.Document, did, "Document")
    if not doc_visible(ctx, d):
        raise HTTPException(403, "You don't have access to this document")
    if not d.file_path:
        raise HTTPException(404, "This document has no file")
    ctx.audit("document.open", "document", d.id, d.company_id, title=d.title)
    ctx.db.commit()
    return {"path": f"/api/files/{d.id}?t={create_file_token(d.id, ctx.user.id)}", "expires_in": 300}


# ================================================================ AI help desk
class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


STOP = {"the", "a", "an", "is", "are", "what", "how", "do", "does", "i", "my", "me", "of", "for", "to", "in",
        "on", "and", "or", "can", "much", "many", "our", "we", "it", "be", "have", "has", "with", "at", "about"}


def _search_docs(ctx: Ctx, text: str, limit: int = 3) -> list[tuple[m.Document, str]]:
    words = [w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in STOP]
    scored = []
    for d in ctx.db.scalars(select(m.Document).where(m.Document.body_text.is_not(None),
                                                     m.Document.category.in_(["policy", "handbook", "sop", "training", "form"]))):
        if not doc_visible(ctx, d) or d.person_id:
            continue
        body = (d.body_text or "").lower()
        score = sum(body.count(w) + 3 * d.title.lower().count(w) for w in words)
        if score:
            # excerpt around the best matching word
            pos = min((body.find(w) for w in words if body.find(w) >= 0), default=0)
            start = max(0, pos - 300)
            scored.append((score, d, (d.body_text or "")[start:start + 1200]))
    scored.sort(key=lambda x: -x[0])
    return [(d, ex) for _, d, ex in scored[:limit]]


def _my_facts(ctx: Ctx) -> dict:
    db, p = ctx.db, me_person(ctx)
    today = _today()
    mgr = db.get(m.Person, p.manager_id) if p.manager_id else None
    hist = attendance_history(None, ctx)
    tasks = list(db.scalars(select(m.Task).where(m.Task.assignee_person_id == p.id, m.Task.status.in_(OPEN))
                            .order_by(m.Task.due_at.nulls_last()).limit(10)))
    return {"name": p.full_name, "designation": p.designation, "employee_code": p.employee_code,
            "manager": mgr.full_name if mgr else None, "leave_balances": _balances(db, p, today.year),
            "attendance_this_month": hist["summary"], "today_shift": _shift_for(db, p, today),
            "open_tasks": [{"title": t.title, "status": t.status, "due": t.due_at.isoformat() if t.due_at else None}
                           for t in tasks],
            "payslips": "Payroll is not in NES GLOBAL OS yet (planned for the next release)."}


def _direct_answer(ctx: Ctx, q: str, facts: dict) -> str | None:
    ql = q.lower()
    bal = {b["kind"]: b for b in facts["leave_balances"]}
    for kind in ("casual", "annual", "sick"):
        if kind in ql and "leave" in ql:
            b = bal.get(kind)
            if b:
                pend = f", {b['pending']:g} pending approval" if b["pending"] else ""
                return (f"You have {b['remaining']:g} {b['label'].lower()} day(s) left this year "
                        f"({b['used']:g} used of {b['entitled']:g}{pend}).")
    if "leave" in ql and any(w in ql for w in ("left", "balance", "remaining", "how many")):
        return "Your leave balance this year:\n" + "\n".join(
            f"- {b['label']}: {b['remaining']:g} left ({b['used']:g} used of {b['entitled']:g})" for b in facts["leave_balances"])
    if "task" in ql:
        t = facts["open_tasks"]
        return ("Your open tasks:\n" + "\n".join(f"- {x['title']} ({x['status'].replace('_', ' ')})" for x in t)) if t \
            else "You have no open tasks right now."
    if "attendance" in ql or "late" in ql or "absent" in ql:
        s = facts["attendance_this_month"]
        return "This month: " + (", ".join(f"{v} {k}" for k, v in s.items()) if s else "no attendance records yet.")
    if "manager" in ql or "report to" in ql:
        return f"You report to {facts['manager']}." if facts["manager"] else "No reporting manager is set for you yet. Ask HR."
    if "shift" in ql or "timing" in ql or "office hours" in ql:
        s = facts["today_shift"]
        return "You're off today." if s["off"] else f"Today: {s['start']}–{s['end']} ({s['note'] or 'shift'})."
    if any(w in ql for w in ("payslip", "salary slip", "pay slip", "loan balance", "advance balance", "tax deduction")):
        return facts["payslips"]
    return None


@router.post("/assistant")
def assistant(body: AskIn, ctx: Ctx = Depends(current_ctx)):
    facts = _my_facts(ctx)
    direct = _direct_answer(ctx, body.question, facts)
    docs = _search_docs(ctx, body.question)
    sources = [{"id": str(d.id), "title": d.title} for d, _ in docs]
    agent = ctx.db.scalar(select(m.Agent).where(m.Agent.code == HELP_DESK_CODE))
    status = operational_status(ctx.db, agent)["operational"] if agent else "NOT CONFIGURED"
    if direct and not docs:
        answer, source = direct, "data"
    elif agent and status in {"OPERATIONAL", "DEGRADED (FALLBACK)"}:
        run = run_agent(ctx.db, agent,
                        "An employee asks:\n" + body.question + "\n\nAnswer briefly and kindly in simple English. Use ONLY "
                        "their own data and the company documents provided. Quote the policy name you used. If the "
                        "answer isn't in the documents, say so and suggest asking HR. Never guess numbers.",
                        "assistant", data_context={"employee": facts, "verified_answer": direct,
                                                   "company_documents": [{"title": d.title, "excerpt": ex} for d, ex in docs]},
                        actor_user_id=ctx.user.id, max_tokens=700)
        ctx.db.commit()
        if run.status == "succeeded" and run.output:
            answer, source = run.output, "ai"
        else:
            answer, source = direct or _doc_fallback(docs), "data"
    else:
        answer, source = direct or _doc_fallback(docs), "data"
    if source == "data" and direct:
        sources = []  # answered from the employee's own records, not from a document
    ctx.audit("assistant.employee_ask", "assistant", None, None, question=body.question[:200], source=source)
    ctx.db.commit()
    return {"answer": answer, "source": source, "sources": sources}


def _doc_fallback(docs) -> str:
    if not docs:
        return ("I couldn't find that in your data or the company documents. Please ask HR, or check the Documents "
                "section.")
    d, ex = docs[0]
    return f"From “{d.title}”:\n\n{ex.strip()}\n\n(Open Documents to read the full text.)"
