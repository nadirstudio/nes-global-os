"""Command Centre data, system health, integrations and audit log."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .. import models as m
from ..ai.runtime import get_setting, put_setting
from ..config import settings
from ..db import get_db
from ..deps import Ctx, get_redis, require
from ..intelligence import department_performance, snapshot
from ..util import row

router = APIRouter(tags=["system"])

INTEGRATIONS = {
    "google_gmail": "Gmail", "google_drive": "Google Drive", "google_sheets": "Google Sheets",
    "google_calendar": "Google Calendar", "google_forms": "Google Forms", "google_docs": "Google Docs",
    "google_apps_script": "Google Apps Script", "whatsapp_cloud": "WhatsApp Business Cloud API",
    "n8n": "n8n automation", "object_storage": "Cloud object storage (documents)",
    "cloud_sync": "Local ↔ cloud database sync", "offsite_backup": "Off-site encrypted backups",
    "web_search": "Web research provider",
}
STATUSES = {"CONNECTED", "NOT CONNECTED", "ERROR", "AUTHENTICATION REQUIRED", "PAUSED"}

DAILY_OPS_DEFAULT = {
    "workdays": [0, 1, 2, 3, 4, 5], "office_start": "09:00", "office_end": "17:00",
    "jobs": {"ceo_briefing": "08:45", "attendance_check": "09:30", "task_recommendations": "09:15",
             "progress_report": "16:30", "daily_close": "17:00", "agent_queue_minutes": 10},
}


def health(db: Session) -> dict:
    out = {}
    try:
        db.execute(text("select 1"))
        out["database"] = "CONNECTED"
    except Exception as e:  # pragma: no cover
        out["database"] = f"ERROR: {e.__class__.__name__}"
    out["redis"] = "CONNECTED" if get_redis() else "NOT CONNECTED"
    hb = get_setting(db, "worker_heartbeat", {})
    if hb.get("at"):
        age = datetime.now(timezone.utc) - datetime.fromisoformat(hb["at"])
        out["worker"] = "CONNECTED" if age < timedelta(minutes=3) else f"ERROR: last heartbeat {int(age.total_seconds()//60)} min ago"
    else:
        out["worker"] = "NOT CONNECTED"
    du = shutil.disk_usage("/")
    out["disk_free_pct"] = round(100 * du.free / du.total)
    bk = get_setting(db, "last_backup", {})
    out["last_backup"] = bk.get("at")
    out["site_role"] = settings.site_role
    out["sync"] = (db.get(m.Integration, "cloud_sync").status if db.get(m.Integration, "cloud_sync") else "NOT CONNECTED")
    return out


@router.get("/health")
def public_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("select 1"))
        return {"ok": True}
    except Exception:
        raise HTTPException(503, "database unavailable")


@router.get("/dashboard")
def dashboard(ctx: Ctx = Depends(require("dashboard.view"))):
    snap = snapshot(ctx.db, ctx.scope)
    feed_q = select(m.AuditLog).order_by(m.AuditLog.at.desc()).limit(40)
    feed = []
    for a in ctx.db.scalars(feed_q):
        if a.company_id and not ctx.scope.allows_company(a.company_id):
            continue
        if ctx.scope.company_ids is not None and not a.company_id:
            continue
        if a.action.startswith("auth."):
            continue
        feed.append({"at": a.at.isoformat(), "actor": a.actor_label, "action": a.action, "entity": a.entity,
                     "detail": a.detail, "agent": bool(a.actor_agent_id)})
    return {"snapshot": snap, "departments": department_performance(ctx.db, ctx.scope),
            "activity": feed[:25], "health": health(ctx.db)}


@router.get("/integrations")
def integrations(ctx: Ctx = Depends(require("integrations.view"))):
    return [row(i) for i in ctx.db.scalars(select(m.Integration).order_by(m.Integration.name))]


class IntegrationPatch(BaseModel):
    status: str
    detail: str | None = None


@router.patch("/integrations/{key}")
def set_integration(key: str, body: IntegrationPatch, ctx: Ctx = Depends(require("integrations.manage"))):
    """Only PAUSED / NOT CONNECTED can be set manually. CONNECTED is set by a successful connector check."""
    i = ctx.db.get(m.Integration, key)
    if not i:
        raise HTTPException(404, "Unknown integration")
    if body.status not in {"PAUSED", "NOT CONNECTED"}:
        raise HTTPException(400, "Status CONNECTED can only be set by a verified connection, not manually")
    i.status, i.detail, i.last_checked_at = body.status, body.detail, datetime.now(timezone.utc)
    ctx.audit("integration.update", "integration", key, None, status=body.status)
    ctx.db.commit()
    return row(i)


@router.get("/settings/daily-ops")
def get_ops(ctx: Ctx = Depends(require("dashboard.view"))):
    return get_setting(ctx.db, "daily_ops", DAILY_OPS_DEFAULT)


@router.put("/settings/daily-ops")
def put_ops(body: dict, ctx: Ctx = Depends(require("company.manage"))):
    val = {**DAILY_OPS_DEFAULT, **body}
    for k, v in val["jobs"].items():
        if k != "agent_queue_minutes":
            try:
                datetime.strptime(v, "%H:%M")
            except (TypeError, ValueError):
                raise HTTPException(400, f"{k}: time must be HH:MM")
    put_setting(ctx.db, "daily_ops", val)
    ctx.audit("settings.daily_ops", "setting", "daily_ops", None)
    ctx.db.commit()
    return val


@router.get("/audit")
def audit_log(limit: int = 200, action: str | None = None, ctx: Ctx = Depends(require("audit.view"))):
    q = select(m.AuditLog).order_by(m.AuditLog.at.desc()).limit(min(limit, 2000))
    if action:
        q = q.where(m.AuditLog.action.like(f"{action}%"))
    return [row(a) for a in ctx.db.scalars(q)]
