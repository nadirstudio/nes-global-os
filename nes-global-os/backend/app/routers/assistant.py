"""CEO Executive Assistant + reports."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from .. import models as m
from ..ai.runtime import operational_status, run_agent
from ..deps import Ctx, require
from ..intelligence import briefing_text, department_performance, snapshot, workforce
from ..reports import KINDS, exec_agent, generate
from ..util import get_or_404, row

router = APIRouter(tags=["assistant"])


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=4000)


def _facts(ctx: Ctx, q: str) -> tuple[str, dict]:
    """Deterministic, data-backed answer for the questions the CEO asks most."""
    ql = q.lower()
    snap = snapshot(ctx.db, ctx.scope)
    wf = workforce(ctx.db, ctx.scope)
    depts = department_performance(ctx.db, ctx.scope)
    data = {"snapshot": snap, "workforce": wf, "departments": depts}
    people = wf["people"]

    if re.search(r"pending task|open task|who has.*task", ql):
        rows = sorted([p for p in people if p["open_tasks"]], key=lambda p: -p["open_tasks"])
        return ("Employees with pending tasks:\n" + "\n".join(
            f"- {p['name']}: {p['open_tasks']} open ({p['overdue_tasks']} overdue), {p['utilization_pct']}% of weekly capacity"
            for p in rows) if rows else "No employee currently has open tasks."), data
    if re.search(r"unused capacity|spare capacity|underutil|free time|idle|awaiting", ql):
        rows = [p for p in people if {"underutilized", "awaiting_assignment"} & set(p["flags"])]
        return ("People with unused capacity this week:\n" + "\n".join(
            f"- {p['name']} ({p['skill_level']}): {p['load_h']}h of {p['capacity_h']}h planned"
            + (" — no open tasks" if "awaiting_assignment" in p["flags"] else "") for p in rows)
            if rows else "Nobody is under 40% planned capacity this week."), data
    if re.search(r"overload|burn|too much work", ql):
        rows = [p for p in people if "overloaded" in p["flags"]]
        return ("Overloaded this week:\n" + "\n".join(f"- {p['name']}: {p['utilization_pct']}%" for p in rows)
                if rows else "Nobody is over 100% planned capacity this week."), data
    if re.search(r"underperform|weak department|struggling|department.*perform", ql):
        bad = [d for d in depts if d["health"] in {"critical", "attention"}]
        nodata = [d for d in depts if d["health"] == "no_data"]
        txt = ("Departments needing attention:\n" + "\n".join(
            f"- {d['company']} / {d['name']}: {d['overdue']} overdue of {d['open']} open"
            + (f", on-time {d['on_time_rate']}%" if d["on_time_rate"] is not None else "") for d in bad)
            if bad else "No department is currently flagged (no overdue work).")
        if nodata:
            txt += f"\n\n{len(nodata)} departments have no tasks recorded yet, so their performance can't be judged."
        return txt, data
    if re.search(r"project.*attention|attention.*project|projects? (at risk|need)", ql):
        rows = [p for p in snap["projects"] if p["needs_attention"]]
        return ("Projects needing your attention:\n" + "\n".join(f"- {p['name']}: {p['why']}" for p in rows)
                if rows else "No active project is flagged right now."), data
    if re.search(r"training", ql):
        rows = [p for p in people if p["pending_training"]]
        return ("Pending training:\n" + "\n".join(f"- {p['name']}: {', '.join(p['pending_training'])}" for p in rows)
                if rows else "No pending training recorded."), data
    if re.search(r"profitable|top service|best service|most revenue", ql):
        fin = snap["finance"]
        if not fin["has_data"]:
            return "No revenue entries are recorded for this month yet, so profitability can't be calculated. " \
                   "Record revenue with the service name in Finance to enable this.", data
    if re.search(r"create (a )?(new )?department|add (a )?department", ql):
        return ("I can't create a department from chat without your explicit confirmation. Open "
                "Organisation → Add department (company, code, name, head). I'll then propose the AI coordinator "
                "and specialist agents for it."), data
    return briefing_text(snap, "Group status"), data


@router.post("/assistant/ask")
def ask(body: AskIn, ctx: Ctx = Depends(require("assistant.use"))):
    facts, data = _facts(ctx, body.question)
    agent = exec_agent(ctx.db)
    status = operational_status(ctx.db, agent) if agent else {"operational": "NOT CONFIGURED", "reason": "Executive Assistant agent missing"}
    answer, source, run_info = facts, "data-only", None
    if agent and status["operational"] in {"OPERATIONAL", "DEGRADED (FALLBACK)"}:
        run = run_agent(ctx.db, agent,
                        "The CEO asks:\n" + body.question + "\n\nA verified data answer has been computed:\n" + facts +
                        "\n\nAnswer as the CEO's Chief of Staff using ONLY the system data. Give recommendations where "
                        "useful and say clearly what data is missing. Do not claim any action was taken.",
                        "assistant", data_context=data, actor_user_id=ctx.user.id, max_tokens=1500)
        run_info = row(run)
        if run.status == "succeeded" and run.output:
            answer, source = run.output, f"ai:{run.model}"
    ctx.audit("assistant.ask", "assistant", None, None, question=body.question[:200], source=source)
    ctx.db.commit()
    return {"answer": answer, "facts": facts, "source": source, "assistant_status": status, "run": run_info}


@router.get("/reports")
def list_reports(kind: str | None = None, ctx: Ctx = Depends(require("reports.view"))):
    q = select(m.Report).order_by(m.Report.generated_at.desc()).limit(60)
    if kind:
        q = q.where(m.Report.kind == kind)
    return [{"id": str(r.id), "kind": r.kind, "title": KINDS.get(r.kind, r.kind), "period_start": r.period_start.isoformat(),
             "period_end": r.period_end.isoformat(), "generated_at": r.generated_at.isoformat(),
             "narrative_source": r.narrative_source, "generated_by": r.generated_by} for r in ctx.db.scalars(q)]


@router.get("/reports/{rid}")
def get_report(rid: str, ctx: Ctx = Depends(require("reports.view"))):
    r = get_or_404(ctx.db, m.Report, rid, "Report")
    return row(r, title=KINDS.get(r.kind, r.kind))


class GenIn(BaseModel):
    kind: str


@router.post("/reports/generate", status_code=201)
def generate_report(body: GenIn, ctx: Ctx = Depends(require("reports.view"))):
    if body.kind not in KINDS:
        raise HTTPException(400, "Unknown report kind")
    rep = generate(ctx.db, body.kind, generated_by=ctx.user.email)
    ctx.audit("report.generate", "report", rep.id, None, kind=body.kind)
    ctx.db.commit()
    return row(rep, title=KINDS[body.kind])
