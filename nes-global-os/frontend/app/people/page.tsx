"use client";
import { useMemo, useState } from "react";
import Shell, { can, useMe } from "@/components/Shell";
import { LEVELS, PersonDrawer } from "@/components/Drawers";
import { Badge, Card, Empty, Err, FormModal, useLoad } from "@/components/ui";
import { api, fmt } from "@/lib/api";

function People() {
  const me = useMe();
  const { data, error, reload } = useLoad<any[]>("/people");
  const companies = useLoad<any[]>("/companies");
  const depts = useLoad<any[]>("/departments");
  const meta = useLoad<any>("/meta/workforce");
  const att = useLoad<any>("/attendance");
  const [open, setOpen] = useState<string | null>(null);
  const [add, setAdd] = useState(false);
  const [q, setQ] = useState("");
  const [co, setCo] = useState("");
  const cname = (id: string) => companies.data?.find((c) => c.id === id)?.name || "—";
  const dname = (id: string) => depts.data?.find((d) => d.id === id)?.name || "—";
  const attBy: Record<string, string> = useMemo(() => Object.fromEntries((att.data?.records || []).map((r: any) => [r.person_id, r.status])), [att.data]);
  const rows = (data || []).filter((p) => (!co || p.company_id === co) && (!q || `${p.full_name} ${p.designation} ${p.skills.join(" ")}`.toLowerCase().includes(q.toLowerCase())));

  const mark = async (pid: string, status: string) => { await api("/attendance/mark", { body: { person_id: pid, status } }); att.reload(); };

  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="row between">
        <div className="row" style={{ flex: 1 }}>
          <input placeholder="Search name, designation, skill…" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 300 }} />
          <select value={co} onChange={(e) => setCo(e.target.value)} style={{ maxWidth: 260 }}>
            <option value="">All companies</option>{companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="row">
          <button className="btn" onClick={async () => { await api("/attendance/check-in", { method: "POST" }).catch((e) => alert(e.message)); att.reload(); }}>Check in</button>
          {can(me, "people.manage") && <button className="btn primary" onClick={() => setAdd(true)}>+ Add person</button>}
        </div>
      </div>
      <Err msg={error} />
      <Card title={`Workforce (${rows.length})`} action={<span className="small muted">Attendance for {att.data?.day}</span>}>
        {rows.length ? (
          <div className="scroll" style={{ maxHeight: 640 }}>
            <table className="tbl">
              <thead><tr><th>Name</th><th>Company / department</th><th>Category</th><th>Level</th><th>Login</th><th>Today</th></tr></thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.id} className="click" onClick={() => setOpen(p.id)}>
                    <td><div>{p.full_name}</div><div className="faint small">{p.designation || "—"} · <span className="mono">{p.employee_code}</span></div></td>
                    <td><div className="small">{cname(p.company_id)}</div><div className="faint small">{p.department_id ? dname(p.department_id) : "—"}</div></td>
                    <td className="small">{fmt.label(p.category)}</td>
                    <td><Badge s="info" label={fmt.label(p.skill_level)} /></td>
                    <td>{p.account ? <Badge s={p.account.active ? "active" : "paused"} label={p.account.role} /> : <span className="faint small">none</span>}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      {can(me, "attendance.manage") ? (
                        <select value={attBy[p.id] || "unmarked"} onChange={(e) => mark(p.id, e.target.value)} style={{ padding: "3px 6px", width: 110 }}>
                          {["unmarked", "present", "late", "remote", "leave", "absent"].map((s) => <option key={s} value={s} disabled={s === "unmarked"}>{s}</option>)}
                        </select>
                      ) : <Badge s={attBy[p.id] || "unmarked"} />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>No people yet. Add your team — each person gets onboarding tasks matched to their skill level.</Empty>}
      </Card>
      <PersonDrawer id={open} onClose={() => setOpen(null)} onChanged={reload} />
      {add && (
        <FormModal title="Add person" submitLabel="Add & start onboarding" onClose={() => setAdd(false)}
          fields={[
            { name: "full_name", label: "Full name", required: true }, { name: "designation", label: "Designation" },
            { name: "company_id", label: "Company", type: "select", required: true, options: (companies.data || []).map((c) => ({ value: c.id, label: c.name })) },
            { name: "department_id", label: "Department", type: "select", options: (depts.data || []).map((d) => ({ value: d.id, label: `${d.name} — ${cname(d.company_id)}` })) },
            { name: "category", label: "Employment category", type: "select", required: true, options: (meta.data?.categories || []).map((c: string) => ({ value: c, label: fmt.label(c) })) },
            { name: "skill_level", label: "Skill level", type: "select", required: true, options: LEVELS.map((l) => ({ value: l, label: fmt.label(l) })) },
            { name: "manager_id", label: "Reporting manager", type: "select", options: (data || []).map((p) => ({ value: p.id, label: p.full_name })) },
            { name: "email", label: "Email", type: "email" }, { name: "phone", label: "Phone" },
            { name: "experience_years", label: "Experience (years)", type: "number" }, { name: "weekly_capacity_hours", label: "Weekly capacity (h)", type: "number", help: "Office week Mon–Sat 9–5 = 48h" },
            { name: "skills", label: "Skills", type: "tags", full: true },
            { name: "training_requirements", label: "Training requirements", type: "tags", full: true },
            { name: "responsibilities", label: "Responsibilities", type: "textarea" },
          ]}
          initial={{ category: "permanent", skill_level: "beginner", weekly_capacity_hours: 48, experience_years: 0 }}
          onSubmit={async (v) => {
            if (v.experience_years == null) v.experience_years = 0;
            if (v.weekly_capacity_hours == null) v.weekly_capacity_hours = 48;
            await api("/people", { body: v }); reload();
          }} />
      )}
    </div>
  );
}

export default function Page() {
  return <Shell title="Human Workforce" sub="Profiles, logins, skill levels, attendance and onboarding"><People /></Shell>;
}
