"use client";
import { useState } from "react";
import { api, fmt } from "@/lib/api";
import { can, useMe } from "@/components/Shell";
import { Badge, Drawer, Err, Field, FormModal, Stat, useAction, useLoad } from "@/components/ui";

export const LEVELS = ["beginner", "intermediate", "expert", "team_leader", "department_head"];

export function PersonDrawer({ id, onClose, onChanged }: { id: string | null; onClose: () => void; onChanged?: () => void }) {
  const me = useMe();
  const { data: p, error, reload } = useLoad<any>(id ? `/people/${id}` : null, [id]);
  const [edit, setEdit] = useState(false);
  const [acct, setAcct] = useState(false);
  const meta = useLoad<any>("/meta/workforce");
  const people = useLoad<any[]>(can(me, "people.view") ? "/people" : null);
  const depts = useLoad<any[]>("/departments");
  if (!id) return null;
  const save = async (v: any) => { await api(`/people/${id}`, { method: "PATCH", body: v }); reload(); onChanged?.(); };
  const fields: Field[] = [
    { name: "full_name", label: "Full name", required: true }, { name: "designation", label: "Designation" },
    { name: "email", label: "Email", type: "email" }, { name: "phone", label: "Phone" },
    { name: "category", label: "Employment category", type: "select", options: (meta.data?.categories || []).map((c: string) => ({ value: c, label: fmt.label(c) })) },
    { name: "skill_level", label: "Skill level", type: "select", options: LEVELS.map((l) => ({ value: l, label: fmt.label(l) })) },
    { name: "department_id", label: "Department", type: "select", options: (depts.data || []).filter((d) => d.company_id === p?.company_id).map((d) => ({ value: d.id, label: d.name })) },
    { name: "manager_id", label: "Reporting manager", type: "select", options: (people.data || []).filter((x) => x.id !== id).map((x) => ({ value: x.id, label: x.full_name })) },
    { name: "skills", label: "Skills", type: "tags" }, { name: "weekly_capacity_hours", label: "Weekly capacity (h)", type: "number" },
    { name: "training_requirements", label: "Training requirements", type: "tags" }, { name: "training_completed", label: "Training completed", type: "tags" },
    { name: "achievements", label: "Achievements", type: "tags", full: true },
    { name: "responsibilities", label: "Responsibilities", type: "textarea" },
    { name: "status", label: "Status", type: "select", options: ["onboarding", "active", "inactive"].map((s) => ({ value: s, label: fmt.label(s) })) },
  ];
  return (
    <Drawer open onClose={onClose}>
      <Err msg={error} />
      {p && (
        <div className="stack">
          <div className="row between">
            <div><h1>{p.full_name}</h1><div className="muted small">{p.designation || "—"} · <span className="mono">{p.employee_code}</span></div></div>
            <Badge s={p.status} />
          </div>
          <div className="row"><Badge s="info" label={fmt.label(p.skill_level)} /><Badge s="off" label={fmt.label(p.category)} />
            {p.account ? <Badge s={p.account.active ? "active" : "paused"} label={`login: ${p.account.role}${p.account.mfa ? " · MFA" : ""}`} /> : <Badge s="NOT CONNECTED" label="no login" />}</div>
          <div className="note">{p.level_guide}</div>
          <div className="grid g3">
            <Stat label="Open tasks" value={p.open_tasks} /><Stat label="Capacity / wk" value={`${p.weekly_capacity_hours}h`} />
            <Stat label="Experience" value={`${p.experience_years}y`} />
          </div>
          <dl className="kv">
            <dt>Email</dt><dd>{p.email || "—"}</dd><dt>Phone</dt><dd>{p.phone || "—"}</dd>
            <dt>Skills</dt><dd>{p.skills.join(", ") || "—"}</dd>
            <dt>Training pending</dt><dd>{p.training_requirements.filter((t: string) => !p.training_completed.includes(t)).join(", ") || "—"}</dd>
            <dt>Achievements</dt><dd>{p.achievements.join(", ") || "—"}</dd>
            <dt>Supervises agents</dt><dd>{p.supervised_agents.map((a: any) => a.name).join(", ") || "—"}</dd>
            <dt>Responsibilities</dt><dd style={{ whiteSpace: "pre-wrap" }}>{p.responsibilities || "—"}</dd>
          </dl>
          <div className="row">
            {can(me, "people.manage") && <button className="btn" onClick={() => setEdit(true)}>Edit profile</button>}
            {can(me, "users.manage") && <button className="btn" onClick={() => setAcct(true)}>{p.account ? "Manage login" : "Create login"}</button>}
          </div>
          <h2 style={{ marginTop: 8 }}>Tasks</h2>
          {p.tasks.length ? (
            <table className="tbl"><tbody>{p.tasks.map((t: any) => (
              <tr key={t.id}><td>{t.title}</td><td><Badge s={t.status} /></td><td className="mono small">{fmt.date(t.due_at)}</td></tr>))}</tbody></table>
          ) : <div className="faint small">No tasks.</div>}
          <h2>Attendance (last 30 records)</h2>
          <div className="row">{p.attendance.length ? p.attendance.map((a: any) => <Badge key={a.id} s={a.status} label={`${a.day.slice(5)} ${a.status}`} />) : <span className="faint small">No records.</span>}</div>
        </div>
      )}
      {edit && p && <FormModal title="Edit profile" fields={fields} initial={p} onSubmit={save} onClose={() => setEdit(false)} />}
      {acct && p && (p.account ? (
        <FormModal title="Manage login" initial={{ role: p.account.role, is_active: p.account.active }} onClose={() => setAcct(false)}
          fields={[{ name: "role", label: "Role", type: "select", options: (meta.data?.roles || []).filter((r: string) => r !== "ceo").map((r: string) => ({ value: r, label: fmt.label(r) })) },
            { name: "is_active", label: "Login enabled", type: "checkbox" },
            { name: "reset_password", label: "Reset password (optional)", type: "password", help: "10+ chars, 3 of: upper, lower, digit, symbol" }]}
          onSubmit={async (v) => { if (p.account.role === "ceo") { delete v.role; delete v.is_active; } await api(`/people/${id}/account`, { method: "PATCH", body: v }); reload(); }} />
      ) : (
        <FormModal title="Create login" initial={{ email: p.email }} onClose={() => setAcct(false)} submitLabel="Create"
          fields={[{ name: "email", label: "Login email", type: "email", required: true },
            { name: "role", label: "Role", type: "select", required: true, options: (meta.data?.roles || []).filter((r: string) => r !== "ceo").map((r: string) => ({ value: r, label: fmt.label(r) })) },
            { name: "temporary_password", label: "Temporary password", type: "password", required: true, help: "Share it privately; they should change it on first sign-in." }]}
          onSubmit={async (v) => { await api(`/people/${id}/account`, { body: v }); reload(); }} />
      ))}
    </Drawer>
  );
}

export function agentFields(catalog: any, companies: any[], depts: any[], people: any[]): Field[] {
  return [
    { name: "name", label: "Agent name", required: true },
    { name: "designation", label: "Designation" },
    { name: "company_id", label: "Company", type: "select", required: true, options: companies.map((c) => ({ value: c.id, label: c.name })) },
    { name: "department_id", label: "Department", type: "select", options: depts.map((d) => ({ value: d.id, label: `${d.name} (${companies.find((c) => c.id === d.company_id)?.code || ""})` })) },
    { name: "provider", label: "Model provider", type: "select", required: true, options: Object.entries(catalog?.providers || {}).map(([k, v]) => ({ value: k, label: String(v) })) },
    { name: "model", label: "Model", required: true, help: "Claude: claude-opus-5-5 · claude-sonnet-5-5 · claude-haiku-5-5" },
    { name: "supervisor_person_id", label: "Human supervisor", type: "select", options: people.map((p) => ({ value: p.id, label: p.full_name })) },
    { name: "monthly_budget", label: "Monthly budget (USD)", type: "number" },
    { name: "daily_token_limit", label: "Daily token limit", type: "number" },
    { name: "is_coordinator", label: "Department coordinator", type: "checkbox" },
    { name: "job_description", label: "Job description", type: "textarea" },
    { name: "responsibilities", label: "Responsibilities", type: "tags", full: true },
    { name: "instructions", label: "Instructions", type: "textarea" },
    { name: "knowledge", label: "Knowledge base (approved facts)", type: "textarea" },
    { name: "permissions", label: "Permissions", type: "tags", full: true,
      help: `Automatic: ${Object.keys(catalog?.automatic || {}).join(", ")}. Need approval: ${Object.keys(catalog?.needs_approval || {}).join(", ")}. Prohibited actions can never be granted.` },
    { name: "tools", label: "Tools", type: "tags", full: true, help: Object.keys(catalog?.tools || {}).join(", ") },
  ];
}

export function AgentDrawer({ id, onClose, onChanged }: { id: string | null; onClose: () => void; onChanged?: () => void }) {
  const me = useMe();
  const { data: a, error, reload } = useLoad<any>(id ? `/agents/${id}` : null, [id]);
  const catalog = useLoad<any>("/agents/catalog");
  const companies = useLoad<any[]>("/companies");
  const depts = useLoad<any[]>("/departments");
  const people = useLoad<any[]>(can(me, "people.view") ? "/people" : null);
  const act = useAction();
  const [edit, setEdit] = useState(false);
  const [testPrompt, setTestPrompt] = useState("");
  const [lastTest, setLastTest] = useState<any>(null);
  if (!id) return null;
  const manage = can(me, "agents.manage");
  const doAction = (action: string) => act.run(async () => {
    const r: any = await api(`/agents/${id}/${action}`, { method: "POST", body: action === "test" ? (testPrompt ? { prompt: testPrompt } : {}) : undefined });
    if (action === "test") setLastTest(r);
    if (action === "duplicate") alert(`Created ${r.name}`);
    reload(); onChanged?.();
  });
  return (
    <Drawer open onClose={onClose}>
      <Err msg={error} />
      {a && (
        <div className="stack">
          <div className="row between">
            <div><h1>⬡ {a.name}</h1><div className="muted small">{a.designation} · <span className="mono">{a.code}</span> · v{a.version}</div></div>
          </div>
          <div className="row"><Badge s={a.status} label={`lifecycle: ${a.status}`} /><Badge s={a.runtime.operational} />{a.is_coordinator && <Badge s="info" label="coordinator" />}</div>
          {a.runtime.reason && <div className="note">{a.runtime.reason}</div>}
          <div className="grid g3">
            <Stat label="Runs 30d" value={a.metrics.runs_30d} detail={a.metrics.success_rate == null ? "—" : `${a.metrics.success_rate}% success`} />
            <Stat label="Queue" value={a.metrics.queue} detail={`${a.metrics.tasks_done_30d} done 30d`} />
            <Stat label="Cost 30d" value={fmt.usd(a.metrics.cost_30d_usd)} detail={`${fmt.num(a.metrics.tokens_30d)} tokens`} />
          </div>
          <dl className="kv">
            <dt>Model</dt><dd className="mono">{a.provider} / {a.model}</dd>
            <dt>Fallbacks</dt><dd className="mono">{a.fallbacks.map((f: any) => `${f.provider}/${f.model}`).join(", ") || "—"}</dd>
            <dt>Permissions</dt><dd>{a.permissions.join(", ") || "—"}</dd>
            <dt>Tools</dt><dd>{a.tools.join(", ") || "—"}</dd>
            <dt>Budget</dt><dd>{a.monthly_budget != null ? `$${a.monthly_budget}/month` : "group budget only"} · {a.daily_token_limit ? `${fmt.num(a.daily_token_limit)} tokens/day` : "no daily cap"}</dd>
            <dt>Last test</dt><dd>{a.last_tested_at ? `${fmt.dt(a.last_tested_at)} — ${a.last_test_ok ? "passed" : "failed"}` : "never"}</dd>
            <dt>Responsibilities</dt><dd>{a.responsibilities.map((r: string) => <div key={r}>• {r}</div>)}</dd>
            <dt>Instructions</dt><dd style={{ whiteSpace: "pre-wrap" }}>{a.instructions || "—"}</dd>
          </dl>
          {manage && (
            <>
              <h2>Lifecycle</h2>
              <label className="f">Test prompt (optional)<input value={testPrompt} onChange={(e) => setTestPrompt(e.target.value)} placeholder="Default: introduce yourself and list responsibilities" /></label>
              <div className="row">
                <button className="btn" disabled={act.busy || a.status === "archived"} onClick={() => setEdit(true)}>Configure / update</button>
                <button className="btn primary" disabled={act.busy || a.status === "archived"} onClick={() => doAction("test")}>{act.busy ? "Running…" : "Test (live call)"}</button>
                <button className="btn" disabled={act.busy || !a.last_test_ok || ["active", "archived"].includes(a.status)} onClick={() => doAction(a.status === "paused" ? "restart" : "activate")}>{a.status === "paused" ? "Restart" : "Activate"}</button>
                <button className="btn" disabled={act.busy || a.status !== "active"} onClick={() => doAction("pause")}>Pause</button>
                <button className="btn" disabled={act.busy} onClick={() => doAction("duplicate")}>Duplicate</button>
                <button className="btn danger" disabled={act.busy || a.status === "archived"} onClick={() => confirm("Archive this agent? Its queued tasks return to humans.") && doAction("archive")}>Archive</button>
              </div>
              <Err msg={act.err} />
              {lastTest && (
                <div className="stack" style={{ gap: 6 }}>
                  <Badge s={lastTest.ok ? "succeeded" : "failed"} label={lastTest.ok ? "Test passed" : "Test failed"} />
                  <pre className="out">{lastTest.ok ? lastTest.run.output : lastTest.run.error}</pre>
                </div>
              )}
            </>
          )}
          <h2>Task queue</h2>
          {a.queue.length ? a.queue.map((t: any) => <div key={t.id} className="row between small"><span>{t.title}</span><Badge s={t.status} /></div>) : <div className="faint small">Empty.</div>}
          <h2>Execution history</h2>
          {a.runs.length ? (
            <table className="tbl"><thead><tr><th>When</th><th>Trigger</th><th>Status</th><th>Tokens</th><th>Cost</th></tr></thead><tbody>
              {a.runs.map((r: any) => (
                <tr key={r.id} title={r.error || r.output?.slice(0, 400) || ""}><td className="small">{fmt.dt(r.started_at)}</td><td>{r.trigger}</td><td><Badge s={r.status} /></td>
                  <td className="mono small">{r.input_tokens + r.output_tokens}</td><td className="mono small">{r.priced ? fmt.usd(r.cost) : "unpriced"}</td></tr>))}
            </tbody></table>
          ) : <div className="faint small">No runs yet.</div>}
        </div>
      )}
      {edit && a && (
        <FormModal title={`Configure ${a.name}`} initial={a} onClose={() => setEdit(false)}
          fields={agentFields(catalog.data, companies.data || [], depts.data || [], people.data || []).filter((f) => f.name !== "company_id")}
          onSubmit={async (v) => { delete v.company_id; await api(`/agents/${id}`, { method: "PATCH", body: v }); reload(); onChanged?.(); }} />
      )}
    </Drawer>
  );
}
