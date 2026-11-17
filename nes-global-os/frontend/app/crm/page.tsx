"use client";
import { useEffect, useState } from "react";
import Shell, { can, useMe } from "@/components/Shell";
import { Badge, Card, Drawer, Empty, Err, FormModal, useAction, useLoad } from "@/components/ui";
import { api, ApiError, fmt } from "@/lib/api";

function CRM() {
  const me = useMe();
  const companies = useLoad<any[]>("/companies");
  const pipes = useLoad<any[]>("/crm/pipelines");
  const [co, setCo] = useState("");
  useEffect(() => { if (!co && companies.data?.length) setCo((companies.data.find((c) => c.kind !== "parent") || companies.data[0]).id); }, [companies.data, co]);
  const [status, setStatus] = useState("open");
  const leads = useLoad<any[]>(co ? `/crm/leads?company_id=${co}&status=${status}` : null, [co, status]);
  const customers = useLoad<any[]>(co ? `/crm/customers?company_id=${co}` : null, [co]);
  const people = useLoad<any[]>(can(me, "people.view") ? "/people" : null);
  const [add, setAdd] = useState(false);
  const [open, setOpen] = useState<any>(null);
  const [view, setView] = useState("pipeline");
  const pipe = pipes.data?.find((p) => p.company_id === co);
  const company = companies.data?.find((c) => c.id === co);
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="row between">
        <div className="row">
          <select value={co} onChange={(e) => setCo(e.target.value)} style={{ maxWidth: 280 }}>{companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
          {["pipeline", "won", "lost", "customers"].map((v) => (
            <button key={v} className={`btn sm ${view === v ? "primary" : ""}`} onClick={() => { setView(v); setStatus(v === "pipeline" || v === "customers" ? "open" : v); }}>{fmt.label(v)}</button>
          ))}
        </div>
        {can(me, "crm.manage") && <button className="btn primary" onClick={() => setAdd(true)}>+ New lead</button>}
      </div>
      <Err msg={leads.error} />
      {view === "pipeline" && (
        pipe ? (
          <div className="kanban">
            {pipe.stages.map((st: string) => {
              const items = (leads.data || []).filter((l) => l.stage === st);
              return (
                <div key={st} className="lane">
                  <h3><span>{st}</span><span className="mono">{items.length}</span></h3>
                  {items.map((l) => (
                    <div key={l.id} className="lcard" onClick={() => setOpen(l)}>
                      <div className="row between"><b style={{ fontWeight: 500 }}>{l.name}</b><span className="mono faint small">{l.score}</span></div>
                      <div className="faint small">{l.service || "—"}</div>
                      <div className="row between small"><span className="mono">{l.value ? fmt.pkr(l.value) : ""}</span>
                        {l.next_follow_up && <span style={{ color: new Date(l.next_follow_up) < new Date() ? "var(--red)" : "var(--muted)" }}>↻ {fmt.date(l.next_follow_up)}</span>}</div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        ) : <Empty>This company has no pipeline yet.</Empty>
      )}
      {(view === "won" || view === "lost") && (
        <Card>{leads.data?.length ? (
          <table className="tbl"><tbody>{leads.data.map((l) => <tr key={l.id} className="click" onClick={() => setOpen(l)}><td>{l.name}</td><td>{l.service}</td><td className="mono">{fmt.pkr(l.value)}</td><td className="small">{fmt.date(l.updated_at)}</td></tr>)}</tbody></table>
        ) : <Empty>None yet.</Empty>}</Card>
      )}
      {view === "customers" && (
        <Card title={`Customers (${customers.data?.length || 0})`}>{customers.data?.length ? (
          <table className="tbl"><thead><tr><th>Name</th><th>Phone</th><th>Email</th><th>Since</th></tr></thead>
            <tbody>{customers.data.map((c) => <tr key={c.id}><td>{c.name}</td><td className="mono small">{c.phone || "—"}</td><td className="small">{c.email || "—"}</td><td className="small">{fmt.date(c.created_at)}</td></tr>)}</tbody></table>
        ) : <Empty>Leads marked as won become customers automatically.</Empty>}</Card>
      )}
      <LeadDrawer lead={open} stages={pipe?.stages || []} onClose={() => setOpen(null)} onChanged={(l) => { setOpen(l); leads.reload(); }} />
      {add && (
        <FormModal title={`New lead — ${company?.name}`} submitLabel="Create lead" onClose={() => setAdd(false)}
          fields={[
            { name: "name", label: "Name", required: true }, { name: "phone", label: "Phone / WhatsApp", help: "03xx numbers are stored as +923xx" },
            { name: "email", label: "Email", type: "email" },
            { name: "service", label: "Service", type: "select", options: (company?.services || []).map((s: string) => ({ value: s, label: s })) },
            { name: "source", label: "Source", type: "select", options: ["WhatsApp", "Walk-in", "Website", "Facebook", "Instagram", "Referral", "Expo", "Phone call", "Email", "Repeat"].map((s) => ({ value: s, label: s })) },
            { name: "value", label: "Estimated value (PKR)", type: "number" },
            { name: "owner_person_id", label: "Owner", type: "select", options: (people.data || []).filter((p) => p.company_id === co).map((p) => ({ value: p.id, label: p.full_name })) },
            { name: "next_follow_up", label: "Next follow-up", type: "datetime-local" },
            { name: "notes", label: "Notes", type: "textarea" },
          ]}
          onSubmit={async (v) => {
            try { await api("/crm/leads", { body: { ...v, company_id: co } }); leads.reload(); }
            catch (e) { const d = (e as ApiError).detail as any; if (d?.existing_id) { const ex = leads.data?.find((l) => l.id === d.existing_id); if (ex) setOpen(ex); } throw e; }
          }} />
      )}
    </div>
  );
}

function LeadDrawer({ lead, stages, onClose, onChanged }: { lead: any; stages: string[]; onClose: () => void; onChanged: (l: any) => void }) {
  const hist = useLoad<any[]>(lead ? `/crm/history?lead_id=${lead.id}` : null, [lead?.id]);
  const act = useAction();
  const [note, setNote] = useState("");
  const [channel, setChannel] = useState("whatsapp");
  if (!lead) return null;
  const patch = (body: any) => act.run(async () => onChanged(await api(`/crm/leads/${lead.id}`, { method: "PATCH", body })));
  return (
    <Drawer open onClose={onClose}>
      <div className="stack">
        <div className="row between"><h1>{lead.name}</h1><Badge s={lead.status} /></div>
        <div className="row"><Badge s="info" label={`score ${lead.score}`} /><Badge s="off" label={lead.source || "source unknown"} /></div>
        <dl className="kv">
          <dt>Phone</dt><dd className="mono">{lead.phone ? <a href={`https://wa.me/${lead.phone.replace("+", "")}`} target="_blank" rel="noreferrer">{lead.phone}</a> : "—"}</dd>
          <dt>Email</dt><dd>{lead.email || "—"}</dd><dt>Service</dt><dd>{lead.service || "—"}</dd>
          <dt>Value</dt><dd>{fmt.pkr(lead.value)}</dd><dt>Follow-up</dt><dd>{fmt.dt(lead.next_follow_up)}</dd>
          <dt>Notes</dt><dd style={{ whiteSpace: "pre-wrap" }}>{lead.notes || "—"}</dd>
        </dl>
        {lead.status === "open" && (
          <>
            <label className="f">Stage<select value={lead.stage} onChange={(e) => patch({ stage: e.target.value })}>{stages.map((s) => <option key={s}>{s}</option>)}</select></label>
            <label className="f">Next follow-up<input type="datetime-local" onChange={(e) => e.target.value && patch({ next_follow_up: new Date(e.target.value).toISOString() })} /></label>
            <div className="row">
              <button className="btn primary" onClick={() => patch({ status: "won" })}>Mark won → customer</button>
              <button className="btn danger" onClick={() => patch({ status: "lost" })}>Mark lost</button>
            </div>
          </>
        )}
        {lead.status !== "open" && <button className="btn" onClick={() => patch({ status: "open" })}>Reopen</button>}
        <Err msg={act.err} />
        <h2>Communication record</h2>
        <div className="row" style={{ flexWrap: "nowrap" }}>
          <select value={channel} onChange={(e) => setChannel(e.target.value)} style={{ width: 120 }}>{["whatsapp", "call", "email", "visit", "meeting", "note"].map((c) => <option key={c}>{c}</option>)}</select>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="What happened?" />
          <button className="btn" disabled={!note} onClick={() => act.run(async () => { await api("/crm/activities", { body: { lead_id: lead.id, channel, summary: note } }); setNote(""); hist.reload(); })}>Log</button>
        </div>
        {hist.data?.length ? hist.data.map((a) => (
          <div key={a.id} className="small" style={{ borderBottom: "1px dashed var(--line)", padding: "6px 0" }}>
            <span className="faint mono">{fmt.dt(a.at)}</span> <Badge s="off" label={a.channel} /> {a.summary}
          </div>
        )) : <div className="faint small">No history yet.</div>}
      </div>
    </Drawer>
  );
}

export default function Page() {
  return <Shell title="CRM & Sales" sub="Separate pipelines for every business unit · duplicate-safe · full communication history"><CRM /></Shell>;
}
