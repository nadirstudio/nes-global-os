"use client";
import { useEffect, useState } from "react";
import Shell, { can, useMe } from "@/components/Shell";
import { Badge, Bar, Card, Drawer, Empty, Err, FormModal, Stat, useAction, useLoad } from "@/components/ui";
import { api, fmt } from "@/lib/api";

function Tasks({ initialOverdue }: { initialOverdue: boolean }) {
  const me = useMe();
  const leader = can(me, "tasks.review") && !me.scope.own_only;
  const [filter, setFilter] = useState(initialOverdue ? "overdue" : leader ? "open" : "mine");
  const path = filter === "overdue" ? "/tasks?overdue=true" : filter === "mine" ? "/tasks?mine=true" : filter === "open" ? "/tasks?status=open" : `/tasks?status=${filter}`;
  const { data, error, reload } = useLoad<any[]>(path, [filter]);
  const companies = useLoad<any[]>("/companies");
  const depts = useLoad<any[]>("/departments");
  const people = useLoad<any[]>(can(me, "people.view") ? "/people" : null);
  const agents = useLoad<any[]>(can(me, "agents.view") ? "/agents" : null);
  const [add, setAdd] = useState(false);
  const [open, setOpen] = useState<any>(null);
  const act = useAction();
  const pname = (id?: string) => people.data?.find((p) => p.id === id)?.full_name;
  const aname = (id?: string) => agents.data?.find((a) => a.id === id)?.name;
  const patch = (id: string, body: any) => act.run(async () => { const t = await api(`/tasks/${id}`, { method: "PATCH", body }); setOpen(t); reload(); });
  return (
    <div className="stack">
      <div className="row between">
        <div className="row">
          {(leader ? ["open", "overdue", "mine", "review", "done"] : ["mine", "review", "done"]).map((f) => (
            <button key={f} className={`btn sm ${filter === f ? "primary" : ""}`} onClick={() => setFilter(f)}>{fmt.label(f)}</button>
          ))}
        </div>
        {can(me, "tasks.create") && <button className="btn primary" onClick={() => setAdd(true)}>+ New task</button>}
      </div>
      <Err msg={error || act.err} />
      <Card>
        {data?.length ? (
          <div className="scroll" style={{ maxHeight: 620 }}>
            <table className="tbl">
              <thead><tr><th>Task</th><th>Owner</th><th>Priority</th><th>Due</th><th>Status</th></tr></thead>
              <tbody>{data.map((t) => (
                <tr key={t.id} className="click" onClick={() => setOpen(t)}>
                  <td><div>{t.title}</div><div className="faint small">{companies.data?.find((c) => c.id === t.company_id)?.name}</div></td>
                  <td className="small">{t.assignee_agent_id ? <>⬡ {aname(t.assignee_agent_id) || "agent"}</> : pname(t.assignee_person_id) || <span className="faint">unassigned</span>}</td>
                  <td><Badge s={t.priority === "urgent" ? "critical" : t.priority === "high" ? "warning" : "off"} label={t.priority} /></td>
                  <td className="mono small" style={{ color: t.overdue ? "var(--red)" : undefined }}>{fmt.date(t.due_at)}</td>
                  <td><Badge s={t.overdue ? "overdue" : t.status} label={t.overdue ? "overdue" : t.status.replace("_", " ")} /></td>
                </tr>))}</tbody>
            </table>
          </div>
        ) : <Empty>No tasks in this view.</Empty>}
      </Card>
      <Drawer open={!!open} onClose={() => setOpen(null)}>
        {open && (
          <div className="stack">
            <h1>{open.title}</h1>
            <div className="row"><Badge s={open.status} /><Badge s="off" label={`${open.complexity} · ${open.estimated_hours}h`} /><Badge s="off" label={`impact ${open.impact}`} /></div>
            <dl className="kv">
              <dt>Owner</dt><dd>{open.assignee_agent_id ? `⬡ ${aname(open.assignee_agent_id)}` : pname(open.assignee_person_id) || "unassigned"}</dd>
              <dt>Reviewer</dt><dd>{pname(open.reviewer_person_id) || "—"}</dd>
              <dt>Due</dt><dd>{fmt.dt(open.due_at)}</dd>
              <dt>Skills</dt><dd>{open.required_skills.join(", ") || "—"}</dd>
              <dt>Description</dt><dd style={{ whiteSpace: "pre-wrap" }}>{open.description || "—"}</dd>
              <dt>Quality / CSAT</dt><dd>{open.quality_score ?? "—"} / {open.customer_satisfaction ?? "—"}</dd>
            </dl>
            {open.result && <><h2>Result</h2><pre className="out">{open.result}</pre></>}
            <div className="row">
              {["todo", "in_progress", "blocked", "review", "done"].map((s) => (
                <button key={s} className={`btn sm ${open.status === s ? "primary" : ""}`} disabled={act.busy} onClick={() => patch(open.id, { status: s })}>{fmt.label(s)}</button>
              ))}
            </div>
            {leader && (
              <>
                <div className="row">
                  <label className="f" style={{ flex: 1 }}>Assign to person
                    <select value={open.assignee_person_id || ""} onChange={(e) => patch(open.id, { assignee_person_id: e.target.value || null })}>
                      <option value="">—</option>{people.data?.filter((p) => p.company_id === open.company_id).map((p) => <option key={p.id} value={p.id}>{p.full_name} ({p.skill_level})</option>)}
                    </select></label>
                  <label className="f" style={{ flex: 1 }}>…or AI agent
                    <select value={open.assignee_agent_id || ""} onChange={(e) => patch(open.id, { assignee_agent_id: e.target.value || null })}>
                      <option value="">—</option>{agents.data?.filter((a) => a.company_id === open.company_id).map((a) => <option key={a.id} value={a.id}>{a.name} — {a.runtime.operational}</option>)}
                    </select></label>
                </div>
                {open.assignee_agent_id && can(me, "agents.run") && (
                  <button className="btn primary" disabled={act.busy} onClick={() => act.run(async () => {
                    const r: any = await api(`/tasks/${open.id}/run-agent`, { method: "POST" }); setOpen(r.task); reload();
                  })}>{act.busy ? "Agent working…" : "Run agent now"}</button>
                )}
                {open.status === "review" || open.status === "done" ? (
                  <div className="row">
                    <label className="f">Quality (1–5)<select value={open.quality_score || ""} onChange={(e) => patch(open.id, { quality_score: Number(e.target.value) })}>
                      <option value="">—</option>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></label>
                    <label className="f">Customer satisfaction (1–5)<select value={open.customer_satisfaction || ""} onChange={(e) => patch(open.id, { customer_satisfaction: Number(e.target.value) })}>
                      <option value="">—</option>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></label>
                  </div>
                ) : null}
              </>
            )}
            <Err msg={act.err} />
          </div>
        )}
      </Drawer>
      {add && (
        <FormModal title="New task" submitLabel="Create task" onClose={() => setAdd(false)}
          fields={[
            { name: "title", label: "Title", required: true, full: true },
            { name: "company_id", label: "Company", type: "select", required: true, options: (companies.data || []).map((c) => ({ value: c.id, label: c.name })) },
            { name: "department_id", label: "Department", type: "select", options: (depts.data || []).map((d) => ({ value: d.id, label: d.name })) },
            { name: "assignee_person_id", label: "Assign to person", type: "select", options: (people.data || []).map((p) => ({ value: p.id, label: p.full_name })) },
            { name: "assignee_agent_id", label: "…or AI agent", type: "select", options: (agents.data || []).map((a) => ({ value: a.id, label: a.name })) },
            { name: "reviewer_person_id", label: "Reviewer", type: "select", options: (people.data || []).map((p) => ({ value: p.id, label: p.full_name })) },
            { name: "due_at", label: "Due", type: "datetime-local" },
            { name: "priority", label: "Priority", type: "select", options: ["low", "medium", "high", "urgent"].map((x) => ({ value: x, label: x })) },
            { name: "impact", label: "Business impact", type: "select", options: ["low", "medium", "high"].map((x) => ({ value: x, label: x })) },
            { name: "complexity", label: "Complexity", type: "select", options: ["basic", "standard", "complex"].map((x) => ({ value: x, label: x })), help: "Beginners only receive basic work" },
            { name: "estimated_hours", label: "Estimated hours", type: "number" },
            { name: "required_skills", label: "Required skills", type: "tags", full: true },
            { name: "description", label: "Description", type: "textarea" },
          ]}
          initial={{ priority: "medium", impact: "medium", complexity: "standard", estimated_hours: 1 }}
          onSubmit={async (v) => { for (const k of ["priority", "impact", "complexity"]) if (!v[k]) delete v[k]; if (v.estimated_hours == null) delete v.estimated_hours; await api("/tasks", { body: v }); reload(); }} />
      )}
    </div>
  );
}

function Approvals() {
  const [status, setStatus] = useState("pending");
  const { data, error, reload } = useLoad<any[]>(`/approvals?status=${status}`, [status]);
  const me = useMe();
  const act = useAction();
  const decide = (id: string, decision: string) => act.run(async () => {
    const note = decision === "rejected" ? prompt("Reason (optional)") || undefined : undefined;
    await api(`/approvals/${id}/decide`, { body: { decision, note } }); reload();
  });
  return (
    <div className="stack">
      <div className="row">{["pending", "approved", "rejected", "all"].map((s) => <button key={s} className={`btn sm ${status === s ? "primary" : ""}`} onClick={() => setStatus(s)}>{fmt.label(s)}</button>)}</div>
      <Err msg={error || act.err} />
      <Card>
        {data?.length ? data.map((a) => (
          <div key={a.id} style={{ borderBottom: "1px solid var(--line)", padding: "10px 0" }}>
            <div className="row between"><b style={{ fontWeight: 500 }}>{a.title}</b><Badge s={a.status} /></div>
            <div className="faint small">{fmt.label(a.kind)} · {a.requested_by ? `requested by ⬡ ${a.requested_by}` : "requested by staff"} · {fmt.dt(a.created_at)}</div>
            {a.payload?.request?.summary && <div className="small" style={{ marginTop: 4 }}>{a.payload.request.summary}</div>}
            {a.decision_note && <div className="small muted">Note: {a.decision_note}</div>}
            {a.status === "pending" && can(me, "approvals.decide") && (
              <div className="row" style={{ marginTop: 8 }}>
                <button className="btn sm primary" disabled={act.busy} onClick={() => decide(a.id, "approved")}>Approve</button>
                <button className="btn sm danger" disabled={act.busy} onClick={() => decide(a.id, "rejected")}>Reject</button>
              </div>
            )}
          </div>
        )) : <Empty>No {status === "all" ? "" : status} approvals.</Empty>}
        <div className="faint small" style={{ marginTop: 8 }}>Approving records your decision. External sending (email/WhatsApp) executes through the matching integration once it is connected.</div>
      </Card>
    </div>
  );
}

function Workforce() {
  const { data, error, reload } = useLoad<any>("/workforce");
  const act = useAction();
  if (error) return <Err msg={error} />;
  if (!data) return <Empty>Analysing workforce…</Empty>;
  const wf = data.workforce, s = wf.summary || {};
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="grid g4">
        <Stat label="Awaiting assignment" value={s.awaiting_assignment || 0} />
        <Stat label="Under-utilised (<40%)" value={s.underutilized || 0} />
        <Stat label="Overloaded (>100%)" value={s.overloaded || 0} state={s.overloaded ? "warn" : undefined} />
        <Stat label="Need training / support" value={`${s.needs_training || 0} / ${s.needs_support || 0}`} />
      </div>
      <Card title="Recommended assignments" action={<span className="small muted">Real unassigned tasks only — review before accepting</span>}>
        <Err msg={act.err} />
        {wf.recommendations.length ? (
          <table className="tbl"><thead><tr><th>Task</th><th>Suggested owner</th><th>Why</th><th /></tr></thead><tbody>
            {wf.recommendations.map((r: any) => (
              <tr key={r.task_id}><td>{r.task}</td><td>{r.person}{r.needs_supervision && <Badge s="warning" label="supervised" />}</td><td className="small muted">{r.reason}</td>
                <td><button className="btn sm primary" disabled={act.busy} onClick={() => act.run(async () => { await api("/workforce/apply", { body: { task_id: r.task_id, person_id: r.person_id } }); reload(); })}>Assign</button></td></tr>
            ))}</tbody></table>
        ) : <Empty>No unassigned tasks need an owner right now.</Empty>}
      </Card>
      <Card title="Utilisation this week" action={<span className="small muted">Measured with quality, on-time rate and customer satisfaction — not task counts alone</span>}>
        {wf.people.length ? (
          <div className="scroll"><table className="tbl"><thead><tr><th>Person</th><th>Load</th><th>Open / overdue</th><th>On-time</th><th>Quality</th><th>CSAT</th><th>Flags</th></tr></thead><tbody>
            {wf.people.sort((a: any, b: any) => b.utilization_pct - a.utilization_pct).map((p: any) => (
              <tr key={p.id}><td><div>{p.name}</div><div className="faint small">{fmt.label(p.skill_level)}</div></td>
                <td style={{ minWidth: 140 }}><div className="mono small">{p.load_h}h / {p.capacity_h}h ({p.utilization_pct}%)</div>
                  <Bar pct={p.utilization_pct} state={p.utilization_pct > 100 ? "crit" : p.utilization_pct > 85 ? "warn" : ""} /></td>
                <td className="mono">{p.open_tasks} / <span style={{ color: p.overdue_tasks ? "var(--red)" : undefined }}>{p.overdue_tasks}</span></td>
                <td className="mono">{p.on_time_rate == null ? "—" : `${p.on_time_rate}%`}</td><td className="mono">{p.avg_quality ?? "—"}</td><td className="mono">{p.avg_csat ?? "—"}</td>
                <td>{p.flags.map((f: string) => <Badge key={f} s={f === "overloaded" || f === "has_overdue" ? "warning" : "info"} label={f.replace(/_/g, " ")} />)}</td></tr>
            ))}</tbody></table></div>
        ) : <Empty>No people in your scope yet.</Empty>}
      </Card>
    </div>
  );
}

function Work() {
  const me = useMe();
  const [tab, setTab] = useState("tasks");
  const [overdue, setOverdue] = useState(false);
  useEffect(() => {
    const p = new URLSearchParams(location.search);
    if (p.get("tab")) setTab(p.get("tab")!);
    if (p.get("overdue")) setOverdue(true);
  }, []);
  const tabs = [["tasks", "Tasks"], ...(can(me, "approvals.view") ? [["approvals", "Approvals"]] : []), ...(can(me, "workforce.intelligence") ? [["workforce", "Workforce intelligence"]] : [])];
  const [att, setAtt] = useState<string | null>(null);
  const attend = async (kind: string) => {
    try { const r: any = await api(`/attendance/${kind}`, { method: "POST" }); setAtt(kind === "check-in" ? `Checked in (${r.status})` : "Checked out"); }
    catch (e) { setAtt((e as Error).message); }
  };
  return (
    <>
      {me.person && (
        <div className="row" style={{ marginBottom: 12 }}>
          <button className="btn sm" onClick={() => attend("check-in")}>Check in</button>
          <button className="btn sm" onClick={() => attend("check-out")}>Check out</button>
          {att && <span className="small muted">{att}</span>}
        </div>
      )}
      <div className="tabs">{tabs.map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "tasks" && <Tasks key={String(overdue)} initialOverdue={overdue} />}
      {tab === "approvals" && <Approvals />}
      {tab === "workforce" && <Workforce />}
    </>
  );
}

export default function Page() {
  return <Shell title="Tasks & Approvals" sub="Assignments for people and AI agents, human approval queue, workforce intelligence"><Work /></Shell>;
}
