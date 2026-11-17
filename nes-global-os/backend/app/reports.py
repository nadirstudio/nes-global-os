"""Daily / weekly / monthly reports. Facts come from intelligence.snapshot; prose optionally from the
Executive Assistant agent, which is only allowed to restate those facts."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .ai.runtime import operational_status, run_agent
from .config import settings
from .intelligence import briefing_text, department_performance, local_today, snapshot, workforce
from .permissions import Scope

EXEC_CODE = "NES-GROUP-EXECUTIVE-ASSISTANT"
ALL = Scope(None, None, None, False)

KINDS = {
    "ceo_briefing": "Daily CEO briefing",
    "progress_report": "Afternoon progress report",
    "daily_close": "Daily closing report",
    "task_recommendations": "Task assignment recommendations",
    "weekly": "Weekly management report",
    "monthly": "Monthly business review",
}


def exec_agent(db: Session) -> m.Agent | None:
    return db.scalar(select(m.Agent).where(m.Agent.code == EXEC_CODE))


def period_for(kind: str, today: date) -> tuple[date, date]:
    if kind == "weekly":
        return today - timedelta(days=today.weekday()), today
    if kind == "monthly":
        return today.replace(day=1), today
    return today, today


def period_stats(db: Session, start: date, end: date) -> dict:
    s = datetime.combine(start, datetime.min.time(), tzinfo=settings.tz)
    e = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=settings.tz)
    done = db.execute(select(m.Company.name, func.count()).select_from(m.Task)
                      .join(m.Company, m.Company.id == m.Task.company_id)
                      .where(m.Task.status == "done", m.Task.completed_at >= s, m.Task.completed_at < e)
                      .group_by(m.Company.name)).all()
    leads_new = db.scalar(select(func.count()).where(m.Lead.created_at >= s, m.Lead.created_at < e)) or 0
    won = db.scalar(select(func.count()).where(m.Lead.status == "won", m.Lead.updated_at >= s, m.Lead.updated_at < e)) or 0
    lost = db.scalar(select(func.count()).where(m.Lead.status == "lost", m.Lead.updated_at >= s, m.Lead.updated_at < e)) or 0
    fin = db.execute(select(m.Company.name, m.FinanceEntry.kind, func.sum(m.FinanceEntry.amount * m.FinanceEntry.fx_to_pkr))
                     .select_from(m.FinanceEntry).join(m.Company, m.Company.id == m.FinanceEntry.company_id)
                     .where(m.FinanceEntry.occurred_on.between(start, end))
                     .group_by(m.Company.name, m.FinanceEntry.kind)).all()
    services = db.execute(select(m.FinanceEntry.service, func.sum(m.FinanceEntry.amount * m.FinanceEntry.fx_to_pkr))
                          .where(m.FinanceEntry.kind == "revenue", m.FinanceEntry.service.is_not(None),
                                 m.FinanceEntry.occurred_on.between(start, end))
                          .group_by(m.FinanceEntry.service).order_by(func.sum(m.FinanceEntry.amount).desc()).limit(5)).all()
    att = dict(db.execute(select(m.Attendance.status, func.count()).where(m.Attendance.day.between(start, end))
                          .group_by(m.Attendance.status)).all())
    ai = db.execute(select(func.count(), func.coalesce(func.sum(m.AgentRun.cost), 0))
                    .where(m.AgentRun.started_at >= s, m.AgentRun.started_at < e)).one()
    finance: dict = {}
    for name, kind, total in fin:
        finance.setdefault(name, {"revenue": 0.0, "expense": 0.0})[kind] = float(total)
    return {"start": start, "end": end, "tasks_completed_by_company": {n: c for n, c in done},
            "leads_new": leads_new, "leads_won": won, "leads_lost": lost,
            "finance_pkr_by_company": finance, "top_services_pkr": [{"service": s_, "revenue": float(v)} for s_, v in services],
            "attendance_records": att, "ai_runs": ai[0], "ai_cost_usd": float(ai[1])}


def generate(db: Session, kind: str, generated_by: str = "system") -> m.Report:
    if kind not in KINDS:
        raise ValueError(kind)
    today = local_today()
    start, end = period_for(kind, today)
    snap = snapshot(db, ALL)
    content = {"snapshot": snap, "departments": department_performance(db, ALL)}
    if kind in {"task_recommendations", "progress_report", "daily_close", "weekly", "monthly"}:
        wf = workforce(db, ALL)
        content["workforce_summary"] = wf["summary"]
        content["recommendations"] = wf["recommendations"]
    if kind in {"weekly", "monthly", "daily_close"}:
        content["period"] = period_stats(db, start, end)
    narrative, source = briefing_text(snap, KINDS[kind]), "data-only"
    if kind == "task_recommendations":
        recs = content["recommendations"]
        narrative = KINDS[kind] + "\n\n" + ("\n".join(f"- {r['task']} → {r['person']} ({r['reason']})"
                                                     + (" [supervised]" if r["needs_supervision"] else "")
                                                     for r in recs) or "No unassigned tasks need an owner.")
    agent = exec_agent(db)
    if agent and kind != "task_recommendations" and operational_status(db, agent)["operational"] in {"OPERATIONAL", "DEGRADED (FALLBACK)"}:
        run = run_agent(db, agent, f"Write the {KINDS[kind]} for the CEO (Mubshair Ali) for {start} to {end}. "
                                   "Use ONLY the system data provided. Lead with what needs a decision, then risks, "
                                   "then highlights. Be concise, use PKR, no invented numbers.",
                        "schedule", data_context=content, max_tokens=1800)
        if run.status == "succeeded" and run.output:
            narrative, source = run.output, f"ai:{run.model}"
    rep = m.Report(kind=kind, period_start=start, period_end=end, content=_json(content),
                   narrative=narrative, narrative_source=source, generated_by=generated_by)
    db.add(rep)
    db.flush()
    return rep


def _json(v):
    from .util import jsonable
    return jsonable(v)
