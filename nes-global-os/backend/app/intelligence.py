"""Corporate intelligence computed purely from the database.

Everything the dashboard, the daily reports and the Executive Assistant say comes from here,
so no figure is ever invented by a model.
"""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import models as m
from .ai.runtime import operational_status, period_starts, provider_status
from .ai.providers import PROVIDERS
from .config import settings
from .permissions import Scope

OPEN = ("todo", "in_progress", "blocked", "review")
LEVEL_RANK = {"beginner": 0, "intermediate": 1, "expert": 2, "team_leader": 3, "department_head": 4}
COMPLEXITY_MIN = {"basic": 0, "standard": 1, "complex": 2}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def local_today() -> date:
    return datetime.now(settings.tz).date()


def is_working_day(d: date) -> bool:
    return d.weekday() != 6  # Sunday off


def _cfilter(q, col, scope: Scope):
    return q if scope.company_ids is None else q.where(col.in_(scope.company_ids or {uuid.uuid4()}))


def _dfilter(q, col, scope: Scope):
    return q if scope.department_ids is None else q.where(col.in_(scope.department_ids or {uuid.uuid4()}))


def f(x) -> float:
    return float(x or 0)


# ---------------------------------------------------------------- workforce engine
def workforce(db: Session, scope: Scope) -> dict:
    people_q = _dfilter(_cfilter(select(m.Person).where(m.Person.status != "inactive"), m.Person.company_id, scope),
                        m.Person.department_id, scope)
    people = list(db.scalars(people_q))
    if not people:
        return {"people": [], "summary": {}, "recommendations": []}
    ids = [p.id for p in people]
    now = _now()
    horizon = now + timedelta(days=7)
    tasks = list(db.scalars(select(m.Task).where(m.Task.assignee_person_id.in_(ids))))
    by_person: dict[uuid.UUID, list[m.Task]] = defaultdict(list)
    for t in tasks:
        by_person[t.assignee_person_id].append(t)

    rows = []
    for p in people:
        ts = by_person[p.id]
        open_ts = [t for t in ts if t.status in OPEN]
        overdue = [t for t in open_ts if t.due_at and t.due_at < now]
        load_h = sum(f(t.estimated_hours) for t in open_ts if not t.due_at or t.due_at <= horizon)
        cap = f(p.weekly_capacity_hours) or 1
        util = round(100 * load_h / cap)
        done_30 = [t for t in ts if t.status == "done" and t.completed_at and t.completed_at >= now - timedelta(days=30)]
        on_time = [t for t in done_30 if not t.due_at or t.completed_at <= t.due_at]
        quals = [t.quality_score for t in done_30 if t.quality_score]
        csat = [t.customer_satisfaction for t in done_30 if t.customer_satisfaction]
        pending_training = [x for x in (p.training_requirements or []) if x not in (p.training_completed or [])]
        flags = []
        if not open_ts:
            flags.append("awaiting_assignment")
        elif util < 40:
            flags.append("underutilized")
        if util > 100:
            flags.append("overloaded")
        if overdue:
            flags.append("has_overdue")
        if pending_training:
            flags.append("needs_training")
        if len(overdue) >= 2 or (quals and sum(quals) / len(quals) < 3):
            flags.append("needs_support")
        rows.append({
            "id": str(p.id), "name": p.full_name, "code": p.employee_code, "designation": p.designation,
            "company_id": str(p.company_id) if p.company_id else None,
            "department_id": str(p.department_id) if p.department_id else None,
            "skill_level": p.skill_level, "category": p.category,
            "capacity_h": cap, "load_h": round(load_h, 1), "utilization_pct": util,
            "open_tasks": len(open_ts), "overdue_tasks": len(overdue),
            "done_30d": len(done_30),
            "on_time_rate": round(100 * len(on_time) / len(done_30)) if done_30 else None,
            "avg_quality": round(sum(quals) / len(quals), 1) if quals else None,
            "avg_csat": round(sum(csat) / len(csat), 1) if csat else None,
            "pending_training": pending_training, "flags": flags,
        })
    summary = Counter(fl for r in rows for fl in r["flags"])
    return {"people": rows, "summary": dict(summary), "recommendations": recommend(db, scope, people, rows)}


def recommend(db: Session, scope: Scope, people: list[m.Person], rows: list[dict]) -> list[dict]:
    """Match unassigned open tasks to people with spare capacity, matching skills and suitable level.
    Beginners only get basic work and always with a reviewer. No busywork is generated: only real tasks."""
    q = _dfilter(_cfilter(select(m.Task).where(m.Task.status == "todo", m.Task.assignee_person_id.is_(None),
                                                m.Task.assignee_agent_id.is_(None)), m.Task.company_id, scope),
                 m.Task.department_id, scope)
    tasks = list(db.scalars(q.order_by(m.Task.due_at.nulls_last())))
    info = {r["id"]: r for r in rows}
    spare = {p.id: info[str(p.id)]["capacity_h"] - info[str(p.id)]["load_h"] for p in people}
    out = []
    prio = {"urgent": 3, "high": 2, "medium": 1, "low": 0}
    for t in sorted(tasks, key=lambda t: (-prio.get(t.priority, 1), t.due_at or datetime.max.replace(tzinfo=timezone.utc))):
        best, best_score, why = None, -1e9, ""
        for p in people:
            if t.company_id != p.company_id:
                continue
            if t.department_id and p.department_id and t.department_id != p.department_id:
                continue
            if LEVEL_RANK.get(p.skill_level, 0) < COMPLEXITY_MIN.get(t.complexity, 1):
                continue
            if spare[p.id] < f(t.estimated_hours):
                continue
            req = {s.lower() for s in t.required_skills or []}
            have = {s.lower() for s in p.skills or []}
            match = len(req & have) / len(req) if req else 0.5
            r = info[str(p.id)]
            quality = (r["avg_quality"] or 3) / 5
            score = 3 * match + 1.5 * quality + spare[p.id] / 40 - r["overdue_tasks"]
            if score > best_score:
                best, best_score = p, score
                why = (f"skills {round(match*100)}% match, {round(spare[p.id],1)}h spare capacity this week"
                       + (f", avg quality {r['avg_quality']}" if r["avg_quality"] else ""))
        if best:
            spare[best.id] -= f(t.estimated_hours)
            out.append({"task_id": str(t.id), "task": t.title, "person_id": str(best.id), "person": best.full_name,
                        "reason": why, "needs_supervision": best.skill_level == "beginner"})
    return out


# ---------------------------------------------------------------- department performance
def department_performance(db: Session, scope: Scope) -> list[dict]:
    q = _dfilter(_cfilter(select(m.Department, m.Company.name).join(m.Company), m.Department.company_id, scope),
                 m.Department.id, scope)
    now = _now()
    since = now - timedelta(days=30)
    out = []
    for d, cname in db.execute(q):
        ts = list(db.scalars(select(m.Task).where(m.Task.department_id == d.id)))
        open_ts = [t for t in ts if t.status in OPEN]
        overdue = [t for t in open_ts if t.due_at and t.due_at < now]
        done = [t for t in ts if t.status == "done" and t.completed_at and t.completed_at >= since]
        on_time = [t for t in done if not t.due_at or t.completed_at <= t.due_at]
        quals = [t.quality_score for t in done if t.quality_score]
        people = db.scalar(select(func.count()).where(m.Person.department_id == d.id, m.Person.status != "inactive"))
        agents = db.scalar(select(func.count()).where(m.Agent.department_id == d.id, m.Agent.status != "archived"))
        has_activity = bool(ts)
        on_time_rate = round(100 * len(on_time) / len(done)) if done else None
        if not has_activity:
            health = "no_data"
        elif overdue and (len(overdue) / max(len(open_ts), 1) > 0.3 or (on_time_rate is not None and on_time_rate < 60)):
            health = "critical"
        elif overdue:
            health = "attention"
        else:
            health = "good"
        out.append({"id": str(d.id), "name": d.name, "company": cname, "company_id": str(d.company_id),
                    "head_person_id": str(d.head_person_id) if d.head_person_id else None,
                    "people": people, "agents": agents, "open": len(open_ts), "overdue": len(overdue),
                    "done_30d": len(done), "on_time_rate": on_time_rate,
                    "avg_quality": round(sum(quals) / len(quals), 1) if quals else None, "health": health})
    return out


# ---------------------------------------------------------------- full snapshot
def snapshot(db: Session, scope: Scope) -> dict:
    now = _now()
    today = local_today()
    day_start, month_start = period_starts()
    C = lambda q, col: _cfilter(q, col, scope)  # noqa: E731

    companies = list(db.scalars(C(select(m.Company), m.Company.id).order_by((m.Company.kind != "parent"), m.Company.name)))
    company_ids = [c.id for c in companies]
    depts = list(db.scalars(_dfilter(C(select(m.Department), m.Department.company_id), m.Department.id, scope)))

    people = list(db.scalars(_dfilter(C(select(m.Person).where(m.Person.status != "inactive"), m.Person.company_id),
                                      m.Person.department_id, scope)))
    agents = list(db.scalars(_dfilter(C(select(m.Agent).where(m.Agent.status != "archived"), m.Agent.company_id),
                                      m.Agent.department_id, scope)))
    op = Counter(operational_status(db, a)["operational"] for a in agents)

    # attendance
    pids = [p.id for p in people]
    att = list(db.scalars(select(m.Attendance).where(m.Attendance.day == today, m.Attendance.person_id.in_(pids)))) if pids else []
    att_c = Counter(a.status for a in att)
    attendance = {"working_day": is_working_day(today), "expected": len(people),
                  "present": att_c["present"] + att_c["remote"], "late": att_c["late"],
                  "leave": att_c["leave"], "absent": att_c["absent"], "unmarked": len(people) - len(att)}

    # tasks
    tq = _dfilter(C(select(m.Task), m.Task.company_id), m.Task.department_id, scope)
    tasks = list(db.scalars(tq))
    open_t = [t for t in tasks if t.status in OPEN]
    overdue_t = [t for t in open_t if t.due_at and t.due_at < now]
    tasks_summary = {
        "open": len(open_t), "todo": sum(t.status == "todo" for t in tasks),
        "in_progress": sum(t.status == "in_progress" for t in tasks),
        "blocked": sum(t.status == "blocked" for t in tasks), "review": sum(t.status == "review" for t in tasks),
        "overdue": len(overdue_t),
        "done_today": sum(1 for t in tasks if t.status == "done" and t.completed_at and t.completed_at >= day_start),
        "unassigned": sum(1 for t in open_t if not t.assignee_person_id and not t.assignee_agent_id),
        "agent_assigned_open": sum(1 for t in open_t if t.assignee_agent_id),
    }
    overdue_list = [{"id": str(t.id), "title": t.title, "due_at": t.due_at, "company_id": str(t.company_id),
                     "assignee_person_id": str(t.assignee_person_id) if t.assignee_person_id else None,
                     "assignee_agent_id": str(t.assignee_agent_id) if t.assignee_agent_id else None}
                    for t in sorted(overdue_t, key=lambda t: t.due_at)[:15]]

    approvals_pending = db.scalar(C(select(func.count()).select_from(m.Approval).where(m.Approval.status == "pending"),
                                    m.Approval.company_id)) or 0

    # CRM
    leads = list(db.scalars(C(select(m.Lead), m.Lead.company_id)))
    open_leads = [l for l in leads if l.status == "open"]
    stage_by_company: dict[str, Counter] = defaultdict(Counter)
    for l in open_leads:
        stage_by_company[str(l.company_id)][l.stage] += 1
    crm = {
        "open_leads": len(open_leads),
        "pipeline_value_pkr": sum(f(l.value) for l in open_leads if l.currency == "PKR"),
        "won_this_month": sum(1 for l in leads if l.status == "won" and l.updated_at >= month_start),
        "lost_this_month": sum(1 for l in leads if l.status == "lost" and l.updated_at >= month_start),
        "new_today": sum(1 for l in leads if l.created_at >= day_start),
        "follow_ups_due": sum(1 for l in open_leads if l.next_follow_up and l.next_follow_up <= now + timedelta(days=1)),
        "follow_ups_overdue": sum(1 for l in open_leads if l.next_follow_up and l.next_follow_up < now),
        "stages_by_company": {k: dict(v) for k, v in stage_by_company.items()},
    }
    customers_total = db.scalar(C(select(func.count()).select_from(m.Customer), m.Customer.company_id)) or 0
    active_customers = db.scalar(C(select(func.count(func.distinct(m.Activity.customer_id)))
                                   .where(m.Activity.customer_id.is_not(None), m.Activity.at >= now - timedelta(days=30)),
                                   m.Activity.company_id)) or 0

    # finance (PKR, converted with recorded fx)
    fin_rows = db.execute(C(select(m.FinanceEntry.company_id, m.FinanceEntry.kind,
                                   func.sum(m.FinanceEntry.amount * m.FinanceEntry.fx_to_pkr))
                            .where(m.FinanceEntry.occurred_on >= month_start.date())
                            .group_by(m.FinanceEntry.company_id, m.FinanceEntry.kind), m.FinanceEntry.company_id)).all()
    fin_by_company: dict[str, dict] = defaultdict(lambda: {"revenue": 0.0, "expense": 0.0})
    for cid, kind, total in fin_rows:
        fin_by_company[str(cid)][kind] = f(total)
    rev = sum(v["revenue"] for v in fin_by_company.values())
    exp = sum(v["expense"] for v in fin_by_company.values())
    outstanding = db.scalar(C(select(func.coalesce(func.sum(m.Invoice.amount - m.Invoice.paid_amount), 0))
                              .where(m.Invoice.status.in_(["issued", "partial"]), m.Invoice.currency == "PKR"),
                              m.Invoice.company_id)) or 0
    overdue_invoices = db.scalar(C(select(func.count()).select_from(m.Invoice)
                                   .where(m.Invoice.status.in_(["issued", "partial"]), m.Invoice.due_on < today),
                                   m.Invoice.company_id)) or 0
    finance = {"month_revenue_pkr": rev, "month_expense_pkr": exp, "month_net_pkr": rev - exp,
               "by_company": dict(fin_by_company), "outstanding_receivables_pkr": f(outstanding),
               "overdue_invoices": overdue_invoices, "has_data": bool(fin_rows)}

    # projects
    projects = list(db.scalars(C(select(m.Project).where(m.Project.status.in_(["planning", "active", "on_hold"])),
                                 m.Project.company_id)))
    proj_rows = []
    for p in projects:
        pt = [t for t in tasks if t.project_id == p.id]
        done = sum(t.status == "done" for t in pt)
        late = p.deadline and p.deadline < today
        near = p.deadline and today <= p.deadline <= today + timedelta(days=7)
        p_over = sum(1 for t in pt if t.status in OPEN and t.due_at and t.due_at < now)
        attention = bool(late or (near and done < len(pt)) or p_over or not p.manager_person_id)
        proj_rows.append({"id": str(p.id), "name": p.name, "status": p.status, "deadline": p.deadline,
                          "tasks": len(pt), "done": done, "overdue_tasks": p_over,
                          "progress_pct": round(100 * done / len(pt)) if pt else 0,
                          "needs_attention": attention,
                          "why": ", ".join(x for x in [
                              "past deadline" if late else "", "deadline within 7 days" if near and done < len(pt) else "",
                              f"{p_over} overdue tasks" if p_over else "", "no project manager" if not p.manager_person_id else ""] if x)})

    # AI usage
    runs_month = db.execute(select(func.count(), func.coalesce(func.sum(m.AgentRun.input_tokens), 0),
                                   func.coalesce(func.sum(m.AgentRun.output_tokens), 0),
                                   func.coalesce(func.sum(m.AgentRun.cost), 0),
                                   func.count().filter(m.AgentRun.priced.is_(False) & (m.AgentRun.status == "succeeded")),
                                   func.count().filter(m.AgentRun.status == "failed"),
                                   func.count().filter(m.AgentRun.status == "blocked"))
                            .where(m.AgentRun.started_at >= month_start)).one()
    ai = {"runs_month": runs_month[0], "input_tokens_month": int(runs_month[1]), "output_tokens_month": int(runs_month[2]),
          "cost_month_usd": f(runs_month[3]), "unpriced_runs": runs_month[4], "failed_runs": runs_month[5],
          "blocked_runs": runs_month[6],
          "providers": {p: provider_status(db, p) for p in PROVIDERS}}

    integrations = {i.key: i.status for i in db.scalars(select(m.Integration))}

    snap = {
        "generated_at": now, "local_date": today, "timezone": settings.timezone,
        "group": {"companies": len(companies), "departments": len(depts), "people": len(people), "agents": len(agents)},
        "companies": [{"id": str(c.id), "code": c.code, "name": c.name, "kind": c.kind, "status": c.status,
                       "parent_id": str(c.parent_id) if c.parent_id else None,
                       "departments": sum(1 for d in depts if d.company_id == c.id),
                       "people": sum(1 for p in people if p.company_id == c.id),
                       "agents": sum(1 for a in agents if a.company_id == c.id),
                       "open_tasks": sum(1 for t in open_t if t.company_id == c.id),
                       "overdue_tasks": sum(1 for t in overdue_t if t.company_id == c.id),
                       "open_leads": sum(1 for l in open_leads if l.company_id == c.id)} for c in companies],
        "workforce": {"by_category": dict(Counter(p.category for p in people)),
                      "by_level": dict(Counter(p.skill_level for p in people))},
        "ai_workforce": {"total": len(agents), "by_lifecycle": dict(Counter(a.status for a in agents)),
                         "by_operational": dict(op), "coordinators": sum(a.is_coordinator for a in agents)},
        "attendance": attendance, "tasks": tasks_summary, "overdue_tasks": overdue_list,
        "approvals_pending": approvals_pending, "crm": crm,
        "customers": {"total": customers_total, "active_30d": active_customers},
        "finance": finance, "projects": proj_rows, "ai_usage": ai, "integrations": integrations,
    }
    snap["alerts"] = alerts(snap)
    return snap


def alerts(s: dict) -> list[dict]:
    a = []

    def add(sev, title, detail):
        a.append({"severity": sev, "title": title, "detail": detail})

    if s["tasks"]["overdue"]:
        add("critical" if s["tasks"]["overdue"] >= 5 else "warning", f"{s['tasks']['overdue']} overdue tasks",
            "Review the overdue list and reassign or reschedule.")
    if s["approvals_pending"]:
        add("warning", f"{s['approvals_pending']} approvals waiting", "Decisions are blocking agents or staff.")
    if s["crm"]["follow_ups_overdue"]:
        add("warning", f"{s['crm']['follow_ups_overdue']} lead follow-ups overdue", "Customers are waiting for a reply.")
    if s["finance"]["overdue_invoices"]:
        add("warning", f"{s['finance']['overdue_invoices']} invoices past due", "Chase receivables.")
    if s["finance"]["has_data"] and s["finance"]["month_net_pkr"] < 0:
        add("critical", "Expenses exceed revenue this month", f"Net PKR {s['finance']['month_net_pkr']:,.0f}")
    att = s["attendance"]
    if att["working_day"] and att["absent"]:
        add("info", f"{att['absent']} absent today", "Check coverage for their tasks.")
    if s["tasks"]["unassigned"]:
        add("info", f"{s['tasks']['unassigned']} tasks have no owner", "Use workforce recommendations to assign.")
    for p in s["projects"]:
        if p["needs_attention"]:
            add("warning", f"Project needs attention: {p['name']}", p["why"])
    provs = s["ai_usage"]["providers"]
    bad = [k for k, v in provs.items() if v in {"AUTHENTICATION REQUIRED", "QUOTA EXHAUSTED", "ERROR"}]
    if bad:
        add("critical", "AI provider problem", ", ".join(f"{k}: {provs[k]}" for k in bad))
    if not any(v in {"CONNECTED", "CONFIGURED (UNTESTED)"} for v in provs.values()):
        add("info", "No AI provider connected", "Agents cannot run until an API key is added in Settings → AI.")
    if s["ai_usage"]["unpriced_runs"]:
        add("info", "AI costs incomplete", f"{s['ai_usage']['unpriced_runs']} runs used models without a price set.")
    if s["ai_workforce"]["by_operational"].get("BUDGET LIMIT"):
        add("warning", "Agents stopped by budget", "Raise budgets or wait for the next period.")
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(a, key=lambda x: order[x["severity"]])


# ---------------------------------------------------------------- data-only briefing text
def briefing_text(s: dict, title: str = "Daily CEO briefing") -> str:
    t, c, fi, att = s["tasks"], s["crm"], s["finance"], s["attendance"]
    lines = [f"{title} — {s['local_date']:%A %d %B %Y}", ""]
    lines.append(f"Group: {s['group']['companies']} companies, {s['group']['departments']} departments, "
                 f"{s['group']['people']} people, {s['group']['agents']} AI agents "
                 f"({s['ai_workforce']['by_operational'].get('OPERATIONAL', 0)} operational).")
    if att["working_day"]:
        lines.append(f"Attendance: {att['present']} present, {att['late']} late, {att['leave']} on leave, "
                     f"{att['absent']} absent, {att['unmarked']} not yet marked.")
    else:
        lines.append("Today is Sunday (office closed).")
    lines.append(f"Work: {t['open']} open tasks ({t['overdue']} overdue, {t['unassigned']} unassigned, "
                 f"{t['blocked']} blocked); {t['done_today']} completed today.")
    lines.append(f"Approvals waiting: {s['approvals_pending']}.")
    lines.append(f"Sales: {c['open_leads']} open leads worth PKR {c['pipeline_value_pkr']:,.0f}; "
                 f"{c['new_today']} new today; {c['won_this_month']} won this month; "
                 f"{c['follow_ups_overdue']} follow-ups overdue.")
    if fi["has_data"]:
        lines.append(f"Finance (month to date): revenue PKR {fi['month_revenue_pkr']:,.0f}, expenses PKR "
                     f"{fi['month_expense_pkr']:,.0f}, net PKR {fi['month_net_pkr']:,.0f}; receivables PKR "
                     f"{fi['outstanding_receivables_pkr']:,.0f}.")
    else:
        lines.append("Finance: no revenue or expense entries recorded this month yet.")
    if s["alerts"]:
        lines += ["", "Needs your attention:"] + [f"- [{a['severity'].upper()}] {a['title']} — {a['detail']}"
                                                   for a in s["alerts"][:8]]
    return "\n".join(lines)
