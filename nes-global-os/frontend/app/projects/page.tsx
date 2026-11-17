"use client";
import { useState } from "react";
import Shell, { can, useMe } from "@/components/Shell";
import { Badge, Bar, Card, Drawer, Empty, Err, FormModal, Stat, useAction, useLoad } from "@/components/ui";
import { api, fmt } from "@/lib/api";

const IDEAS = ["Embassy Appointment Department", "Arduino Course", "Creative Department", "IELTS Course", "PTE Course", "Commercial Printing Store"];

function Projects() {
  const me = useMe();
  const { data, error, reload } = useLoad<any[]>("/projects");
  const companies = useLoad<any[]>("/companies");
  const people = useLoad<any[]>(can(me, "people.view") ? "/people" : null);
  const agents = useLoad<any[]>(can(me, "agents.view") ? "/agents" : null);
  const [add, setAdd] = useState<string | boolean>(false);
  const [open, setOpen] = useState<any>(null);
  const act = useAction();
  const pname = (id?: string) => people.data?.find((p) => p.id === id)?.full_name || "—";
  const existing = new Set((data || []).map((p) => p.name));
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="row between">
        <div className="row small muted">{can(me, "projects.manage") && IDEAS.filter((i) => !existing.has(i)).map((i) => (
          <button key={i} className="btn sm ghost" onClick={() => setAdd(i)}>+ {i}</button>
        ))}</div>
        {can(me, "projects.manage") && <button className="btn primary" onClick={() => setAdd(true)}>+ New project</button>}
      </div>
      <Err msg={error} />
      <div className="grid g3">
        {data?.length ? data.map((p) => (
          <div key={p.id} className="card" style={{ cursor: "pointer" }} onClick={() => setOpen(p)}>
            <div className="row between"><b style={{ fontWeight: 600 }}>{p.name}</b><Badge s={p.status} /></div>
            <div className="faint small">{companies.data?.find((c) => c.id === p.company_id)?.name} · PM {pname(p.manager_person_id)}</div>
            <div style={{ margin: "10px 0 4px" }}><Bar pct={p.stats.tasks ? (100 * p.stats.done) / p.stats.tasks : 0} /></div>
            <div className="row between small"><span>{p.stats.done}/{p.stats.tasks} tasks{p.stats.overdue ? <span style={{ color: "var(--red)" }}> · {p.stats.overdue} overdue</span> : ""}</span><span className="mono">{fmt.date(p.deadline)}</span></div>
            <div className="row between small muted" style={{ marginTop: 4 }}>
              <span>Budget {p.budget ? fmt.pkr(p.budget) : "—"}{p.stats.budget_used_pct != null ? ` (${p.stats.budget_used_pct}% used)` : ""}</span>
              <span>Rev {fmt.pkr(p.stats.revenue_pkr)}</span>
            </div>
          </div>
        )) : <div className="span3"><Empty>No projects yet. Launch one from the suggestions above.</Empty></div>}
      </div>
      <Drawer open={!!open} onClose={() => setOpen(null)}>
        {open && (
          <div className="stack">
            <div className="row between"><h1>{open.name}</h1><Badge s={open.status} /></div>
            <div className="grid g3">
              <Stat label="Tasks" value={`${open.stats.done}/${open.stats.tasks}`} detail={`${open.stats.overdue} overdue`} />
              <Stat label="Expenses" value={fmt.pkr(open.stats.expenses_pkr)} detail={open.budget ? `of ${fmt.pkr(open.budget)}` : "no budget set"} />
              <Stat label="Revenue" value={fmt.pkr(open.stats.revenue_pkr)} />
            </div>
            <dl className="kv">
              <dt>Kind</dt><dd>{fmt.label(open.kind)}</dd><dt>Project manager</dt><dd>{pname(open.manager_person_id)}</dd>
              <dt>Start / deadline</dt><dd>{fmt.date(open.start_on)} → {fmt.date(open.deadline)}</dd>
              <dt>Team</dt><dd>{(open.member_ids || []).map(pname).join(", ") || "—"}</dd>
              <dt>AI agents</dt><dd>{(open.agent_ids || []).map((id: string) => agents.data?.find((a) => a.id === id)?.name).filter(Boolean).join(", ") || "—"}</dd>
              <dt>Objectives</dt><dd style={{ whiteSpace: "pre-wrap" }}>{open.objectives || "—"}</dd>
            </dl>
            {can(me, "projects.manage") && (
              <div className="row">
                {["planning", "active", "on_hold", "done", "cancelled"].map((s) => (
                  <button key={s} className={`btn sm ${open.status === s ? "primary" : ""}`} onClick={() => act.run(async () => { setOpen(await api(`/projects/${open.id}`, { method: "PATCH", body: { status: s } })); reload(); })}>{fmt.label(s)}</button>
                ))}
              </div>
            )}
            <h2>Milestones & deliverables</h2>
            {open.milestones.map((ms: any) => (
              <label key={ms.id} className="row small" style={{ gap: 8 }}>
                <input type="checkbox" style={{ width: 16 }} checked={ms.done} disabled={!can(me, "projects.manage")}
                  onChange={() => act.run(async () => { await api(`/milestones/${ms.id}`, { method: "PATCH", body: { ...ms, done: !ms.done } }); const all = await api<any[]>("/projects"); setOpen(all.find((x) => x.id === open.id)); reload(); })} />
                <span style={{ textDecoration: ms.done ? "line-through" : undefined }}>{ms.title}</span><span className="faint">{ms.deliverable}</span><span className="mono faint">{fmt.date(ms.due_on)}</span>
              </label>
            ))}
            {can(me, "projects.manage") && <MilestoneAdd pid={open.id} onAdded={async () => { const all = await api<any[]>("/projects"); setOpen(all.find((x) => x.id === open.id)); reload(); }} />}
            <a className="btn" href={`/work/`}>Open tasks board →</a>
            <Err msg={act.err} />
          </div>
        )}
      </Drawer>
      {add && (
        <FormModal title="New project" submitLabel="Create project" onClose={() => setAdd(false)} initial={{ name: typeof add === "string" ? add : "", kind: "venture", status: "planning", currency: "PKR" }}
          fields={[
            { name: "name", label: "Name", required: true },
            { name: "company_id", label: "Company", type: "select", required: true, options: (companies.data || []).map((c) => ({ value: c.id, label: c.name })) },
            { name: "kind", label: "Kind", type: "select", options: ["internal", "client", "venture", "white_label"].map((k) => ({ value: k, label: fmt.label(k) })) },
            { name: "manager_person_id", label: "Project manager", type: "select", options: (people.data || []).map((p) => ({ value: p.id, label: p.full_name })) },
            { name: "budget", label: "Budget (PKR)", type: "number" }, { name: "status", label: "Status", type: "select", options: ["planning", "active"].map((k) => ({ value: k, label: k })) },
            { name: "start_on", label: "Start", type: "date" }, { name: "deadline", label: "Deadline", type: "date" },
            { name: "objectives", label: "Objectives", type: "textarea" },
          ]}
          onSubmit={async (v) => { await api("/projects", { body: { ...v, kind: v.kind || "internal", status: v.status || "planning" } }); reload(); }} />
      )}
    </div>
  );
}

function MilestoneAdd({ pid, onAdded }: { pid: string; onAdded: () => void }) {
  const [t, setT] = useState("");
  const [d, setD] = useState("");
  return (
    <div className="row" style={{ flexWrap: "nowrap" }}>
      <input placeholder="New milestone" value={t} onChange={(e) => setT(e.target.value)} />
      <input type="date" value={d} onChange={(e) => setD(e.target.value)} style={{ width: 160 }} />
      <button className="btn" disabled={!t} onClick={async () => { await api(`/projects/${pid}/milestones`, { body: { title: t, due_on: d || null } }); setT(""); setD(""); onAdded(); }}>Add</button>
    </div>
  );
}

export default function Page() {
  return <Shell title="Projects & Ventures" sub="Launch and manage departments, courses, stores, locations and client work"><Projects /></Shell>;
}
