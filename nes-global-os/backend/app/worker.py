"""Background worker: daily corporate operations schedule (Asia/Karachi) + AI agent task queue.

Run with:  python -m app.worker
Several workers may run (local + cloud); job_runs' unique (job, slot) guarantees each job runs once,
and the agent queue uses SELECT … FOR UPDATE SKIP LOCKED.
"""
from __future__ import annotations

import logging
import signal
import time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import models as m
from .ai.runtime import get_setting, put_setting
from .config import settings
from .db import SessionLocal
from .deps import audit
from .reports import generate
from .routers.system import DAILY_OPS_DEFAULT
from .routers.work import _execute_agent_task

log = logging.getLogger("nes.worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
_stop = False


def _claim(db, job: str, slot: str) -> m.JobRun | None:
    jr = m.JobRun(job=job, slot=slot)
    db.add(jr)
    try:
        db.commit()
        return jr
    except IntegrityError:
        db.rollback()
        return None


def _finish(db, jr: m.JobRun, status: str, detail: str | None = None) -> None:
    jr.status, jr.detail, jr.finished_at = status, detail, datetime.now(timezone.utc)
    db.commit()


def last_workday_of_month(d: date, workdays: list[int]) -> bool:
    nxt = d + timedelta(days=1)
    while nxt.month == d.month:
        if nxt.weekday() in workdays:
            return False
        nxt += timedelta(days=1)
    return True


def due_jobs(now_local: datetime, ops: dict) -> list[tuple[str, str]]:
    """Returns (job, slot) pairs that are due now. Pure function — unit tested."""
    d = now_local.date()
    if now_local.weekday() not in ops["workdays"]:
        return []
    out = []
    hhmm = now_local.strftime("%H:%M")
    for job, at in ops["jobs"].items():
        if job == "agent_queue_minutes":
            continue
        if hhmm >= at:
            out.append((job, d.isoformat()))
    close = ops["jobs"]["daily_close"]
    if hhmm >= close and now_local.weekday() == max(ops["workdays"]):
        out.append(("weekly", f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"))
    if hhmm >= close and last_workday_of_month(d, ops["workdays"]):
        out.append(("monthly", d.strftime("%Y-%m")))
    return out


def run_job(db, job: str) -> str:
    if job in {"ceo_briefing", "progress_report", "daily_close", "task_recommendations", "weekly", "monthly"}:
        rep = generate(db, job, generated_by="worker")
        db.commit()
        return f"report {rep.id} ({rep.narrative_source})"
    if job == "attendance_check":
        today = datetime.now(settings.tz).date()
        people = list(db.scalars(select(m.Person.id).where(m.Person.status == "active")))
        marked = set(db.scalars(select(m.Attendance.person_id).where(m.Attendance.day == today)))
        unmarked = len([p for p in people if p not in marked])
        audit(db, "ops.attendance_check", None, None, None, {"unmarked": unmarked}, label="worker")
        db.commit()
        return f"{unmarked} people not yet marked"
    return "unknown job"


def process_agent_queue(db, limit: int = 5) -> int:
    q = (select(m.Task).join(m.Agent, m.Agent.id == m.Task.assignee_agent_id)
         .where(m.Task.status == "todo", m.Agent.status == "active")
         .order_by(m.Task.due_at.nulls_last()).limit(limit).with_for_update(skip_locked=True, of=m.Task))
    n = 0
    for t in list(db.scalars(q)):
        a = db.get(m.Agent, t.assignee_agent_id)
        _execute_agent_task(db, a, t)
        n += 1
    db.commit()
    return n


def tick(now_utc: datetime | None = None) -> dict:
    now_local = (now_utc or datetime.now(timezone.utc)).astimezone(settings.tz)
    done = {"jobs": [], "agent_tasks": 0}
    with SessionLocal() as db:
        put_setting(db, "worker_heartbeat", {"at": datetime.now(timezone.utc).isoformat()})
        db.commit()
        ops = get_setting(db, "daily_ops", DAILY_OPS_DEFAULT)
        for job, slot in due_jobs(now_local, ops):
            jr = _claim(db, job, slot)
            if not jr:
                continue
            try:
                _finish(db, jr, "succeeded", run_job(db, job))
                done["jobs"].append(job)
            except Exception as e:  # keep the worker alive, record the failure truthfully
                db.rollback()
                log.exception("job %s failed", job)
                _finish(db, jr, "failed", f"{e.__class__.__name__}: {e}")
        every = int(ops["jobs"].get("agent_queue_minutes", 10))
        slot = now_local.strftime("%Y-%m-%dT%H:") + f"{(now_local.minute // every) * every:02d}"
        if _claim(db, "agent_queue", slot):
            try:
                done["agent_tasks"] = process_agent_queue(db)
            except Exception:
                db.rollback()
                log.exception("agent queue failed")
    return done


def main() -> None:
    def stop(*_):
        global _stop
        _stop = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("NES worker started (timezone %s)", settings.timezone)
    while not _stop:
        try:
            res = tick()
            if res["jobs"] or res["agent_tasks"]:
                log.info("tick: %s", res)
        except Exception:
            log.exception("tick failed")
        for _ in range(30):
            if _stop:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
