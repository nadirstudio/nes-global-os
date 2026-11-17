"use client";
import { useState } from "react";
import Shell, { can, useMe } from "@/components/Shell";
import { AgentDrawer, agentFields } from "@/components/Drawers";
import { Badge, Card, Empty, Err, FormModal, Stat, useLoad } from "@/components/ui";
import { api } from "@/lib/api";

function Factory() {
  const me = useMe();
  const { data, error, reload } = useLoad<any[]>("/agents");
  const companies = useLoad<any[]>("/companies");
  const depts = useLoad<any[]>("/departments");
  const people = useLoad<any[]>(can(me, "people.view") ? "/people" : null);
  const catalog = useLoad<any>("/agents/catalog");
  const [open, setOpen] = useState<string | null>(null);
  const [add, setAdd] = useState(false);
  const [co, setCo] = useState("");
  const [st, setSt] = useState("");
  const [q, setQ] = useState("");
  const dname = (id: string) => depts.data?.find((d) => d.id === id)?.name || "—";
  const cname = (id: string) => companies.data?.find((c) => c.id === id)?.name || "—";
  const all = data || [];
  const rows = all.filter((a) => (!co || a.company_id === co) && (!st || a.runtime.operational === st) &&
    (!q || `${a.name} ${a.designation}`.toLowerCase().includes(q.toLowerCase())));
  const count = (k: string) => all.filter((a) => a.runtime.operational === k).length;
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="grid g4">
        <Stat label="Agents" value={all.length} detail={`${all.filter((a) => a.is_coordinator).length} department coordinators`} />
        <Stat label="Operational" value={count("OPERATIONAL")} state={count("OPERATIONAL") ? "ok" : undefined} detail="passed live test, provider connected" />
        <Stat label="Need a provider" value={count("NOT CONNECTED")} detail="add an API key in Settings → AI" />
        <Stat label="Problems" value={count("AUTHENTICATION REQUIRED") + count("QUOTA EXHAUSTED") + count("ERROR") + count("BUDGET LIMIT")}
          state={count("AUTHENTICATION REQUIRED") + count("QUOTA EXHAUSTED") + count("ERROR") ? "crit" : undefined} detail="auth / quota / error / budget" />
      </div>
      <div className="note">
        Lifecycle: <b>configure</b> → <b>test</b> (a real model call) → <b>activate</b>. An agent can't be activated until a live test passes, so no agent is ever shown as working when it isn't.
        Agents draft, analyse and recommend; anything external (messages, submissions, publishing, money) goes to the approval queue.
      </div>
      <div className="row between">
        <div className="row" style={{ flex: 1 }}>
          <input placeholder="Search agents…" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 260 }} />
          <select value={co} onChange={(e) => setCo(e.target.value)} style={{ maxWidth: 240 }}>
            <option value="">All companies</option>{companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select value={st} onChange={(e) => setSt(e.target.value)} style={{ maxWidth: 220 }}>
            <option value="">Any status</option>
            {[...new Set(all.map((a) => a.runtime.operational))].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {can(me, "agents.manage") && <button className="btn primary" onClick={() => setAdd(true)}>+ Create agent</button>}
      </div>
      <Err msg={error} />
      <Card title={`Agent registry (${rows.length})`}>
        {rows.length ? (
          <div className="scroll" style={{ maxHeight: 640 }}>
            <table className="tbl">
              <thead><tr><th>Agent</th><th>Company / department</th><th>Model</th><th>Lifecycle</th><th>Runtime</th></tr></thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id} className="click" onClick={() => setOpen(a.id)}>
                    <td><div>{a.is_coordinator ? "◆ " : "⬡ "}{a.name}</div><div className="faint small mono">{a.code}</div></td>
                    <td><div className="small">{cname(a.company_id)}</div><div className="faint small">{a.department_id ? dname(a.department_id) : "—"}</div></td>
                    <td className="mono small">{a.model}{a.fallbacks.length ? <span className="faint"> +{a.fallbacks.length}</span> : null}</td>
                    <td><Badge s={a.status} /></td>
                    <td><Badge s={a.runtime.operational} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>No agents match.</Empty>}
      </Card>
      <AgentDrawer id={open} onClose={() => setOpen(null)} onChanged={reload} />
      {add && (
        <FormModal title="Create AI agent" submitLabel="Create" onClose={() => setAdd(false)}
          fields={agentFields(catalog.data, companies.data || [], depts.data || [], people.data || [])}
          initial={{ provider: "anthropic", model: "claude-sonnet-5-5", permissions: ["research", "draft_document", "internal_report"] }}
          onSubmit={async (v) => { const r: any = await api("/agents", { body: { ...v, is_coordinator: !!v.is_coordinator } }); reload(); setOpen(r.id); }} />
      )}
    </div>
  );
}

export default function Page() {
  return <Shell title="AI Agent Factory" sub="Create, configure, test, activate, pause, duplicate and archive AI agents"><Factory /></Shell>;
}
