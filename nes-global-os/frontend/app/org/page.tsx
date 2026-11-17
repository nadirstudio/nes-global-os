"use client";
import { useState } from "react";
import Shell, { can, useMe } from "@/components/Shell";
import { AgentDrawer, PersonDrawer } from "@/components/Drawers";
import { Badge, Empty, Err, FormModal, tone, useLoad } from "@/components/ui";
import { api } from "@/lib/api";

function Tree() {
  const me = useMe();
  const { data, error, reload } = useLoad<any>("/org/tree");
  const [person, setPerson] = useState<string | null>(null);
  const [agent, setAgent] = useState<string | null>(null);
  const [addDept, setAddDept] = useState<string | null>(null);
  const [addCo, setAddCo] = useState(false);
  const [showAgents, setShowAgents] = useState(true);
  if (error) return <Err msg={error} />;
  if (!data) return <Empty>Loading organisation…</Empty>;

  const P = (p: any) => (
    <span key={p.id} className="chip" onClick={() => setPerson(p.id)} title={`${p.designation || ""} · ${p.level}`}>
      <span className={`dot ${p.status === "active" ? "ok" : "info"}`} />{p.name}<span className="faint">{p.designation ? `· ${p.designation}` : ""}</span>
    </span>
  );
  const A = (a: any) => (
    <span key={a.id} className={`chip agent ${a.coordinator ? "coord" : ""}`} onClick={() => setAgent(a.id)} title={`${a.operational} · ${a.model}`}>
      <span className={`dot ${tone(a.operational)}`} />⬡ {a.name}
    </span>
  );
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="row between">
        <div className="row small muted">
          <span className="chip" style={{ cursor: "default" }}><span className="dot ok" />person</span>
          <span className="chip agent" style={{ cursor: "default" }}><span className="dot off" />AI agent</span>
          <span className="chip agent coord" style={{ cursor: "default" }}>⬡ AI coordinator</span>
          <label className="row" style={{ gap: 6 }}><input type="checkbox" style={{ width: 16 }} checked={showAgents} onChange={(e) => setShowAgents(e.target.checked)} /> show agents</label>
        </div>
        {can(me, "company.manage") && <button className="btn" onClick={() => setAddCo(true)}>+ Company / venture</button>}
      </div>
      {data.ceo && (
        <div className="card row" style={{ gap: 14 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, display: "grid", placeItems: "center", background: "linear-gradient(135deg,#3b82f6,#22d3ee)", fontWeight: 700 }}>CEO</div>
          <div><div style={{ fontWeight: 600, cursor: "pointer" }} onClick={() => setPerson(data.ceo.id)}>{data.ceo.name}</div><div className="muted small">Chief Executive Officer · NADIR E-SKILLS (SMC-PRIVATE) LIMITED</div></div>
        </div>
      )}
      <div className="grid g2">
        {data.companies.map((c: any) => (
          <div key={c.id} className="org-co" style={c.kind === "parent" ? { gridColumn: "1 / -1" } : undefined}>
            <div className="row between">
              <div><b>{c.name}</b> <span className="faint mono small">{c.code}</span></div>
              <div className="row">{c.status !== "active" && <Badge s={c.status} />}
                {can(me, "department.manage") && <button className="btn sm" onClick={() => setAddDept(c.id)}>+ Department</button>}</div>
            </div>
            {c.directors.length > 0 && <div className="small muted" style={{ marginTop: 6 }}>Directors: {c.directors.map(P)}</div>}
            <div style={c.kind === "parent" ? { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "0 18px" } : undefined}>
              {c.departments.map((d: any) => (
                <div key={d.id} className="org-dept">
                  <div className="row between"><span style={{ fontWeight: 500 }}>{d.name}{d.group_wide && <span className="faint small"> · group-wide</span>}</span>
                    <span className="faint small">{d.people.length + (d.head ? 1 : 0)} people · {d.agents.length} AI</span></div>
                  <div className="small">
                    {d.head ? <><span className="faint">Head: </span>{P(d.head)}</> : <span className="faint">No department head assigned</span>}
                  </div>
                  {d.people.length > 0 && <div>{d.people.map(P)}</div>}
                  {showAgents && d.agents.length > 0 && <div>{d.agents.map(A)}</div>}
                </div>
              ))}
            </div>
            {c.unassigned_people.length > 0 && <div className="small" style={{ marginTop: 8 }}><span className="faint">Not in a department: </span>{c.unassigned_people.map(P)}</div>}
          </div>
        ))}
      </div>
      <PersonDrawer id={person} onClose={() => setPerson(null)} onChanged={reload} />
      <AgentDrawer id={agent} onClose={() => setAgent(null)} onChanged={reload} />
      {addDept && (
        <FormModal title="Add department" onClose={() => setAddDept(null)} submitLabel="Create department"
          fields={[{ name: "code", label: "Code", required: true, placeholder: "e.g. IELTS" }, { name: "name", label: "Name", required: true },
            { name: "description", label: "Description", type: "textarea" }]}
          onSubmit={async (v) => { await api("/departments", { body: { ...v, company_id: addDept } }); reload(); }} />
      )}
      {addCo && (
        <FormModal title="Add company / venture" onClose={() => setAddCo(false)} submitLabel="Create"
          fields={[{ name: "code", label: "Code", required: true, placeholder: "NES-PRINT" }, { name: "name", label: "Name", required: true },
            { name: "kind", label: "Kind", type: "select", options: [{ value: "unit", label: "Business unit" }, { value: "venture", label: "Venture / subsidiary" }] },
            { name: "status", label: "Status", type: "select", options: [{ value: "planned", label: "Planned" }, { value: "active", label: "Active" }] },
            { name: "website", label: "Website" }, { name: "phone", label: "Phone" }, { name: "email", label: "Email" },
            { name: "address", label: "Address" }, { name: "services", label: "Services", type: "tags", full: true },
            { name: "description", label: "Description", type: "textarea" }]}
          onSubmit={async (v) => {
            const parent = data.companies.find((c: any) => c.kind === "parent");
            await api("/companies", { body: { ...v, kind: v.kind || "unit", status: v.status || "planned", parent_id: parent?.id } });
            reload();
          }} />
      )}
    </div>
  );
}

export default function Page() {
  return <Shell title="Organisation" sub="Live structure: CEO → companies → departments → people and AI agents. Click anyone to manage them."><Tree /></Shell>;
}
