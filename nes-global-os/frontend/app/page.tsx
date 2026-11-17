"use client";
import { Fragment, useEffect, useState } from "react";
import Shell, { useMe } from "@/components/Shell";
import { Badge, Card, Drawer, Empty, Err, Stat, useLoad } from "@/components/ui";
import { Donut, HBars, NetworkMap } from "@/components/charts";
import { fmt } from "@/lib/api";

const OP_TONE: Record<string, string> = {
  OPERATIONAL: "ok", "DEGRADED (FALLBACK)": "warn", "BUDGET LIMIT": "warn", PAUSED: "warn", "NOT CONNECTED": "off",
  "AUTHENTICATION REQUIRED": "crit", "QUOTA EXHAUSTED": "crit", ERROR: "crit", "NOT ACTIVE": "info", "NOT OPERATIONAL": "off",
  "CONFIGURED (UNTESTED)": "info",
};

function Centre() {
  const me = useMe();
  const { data, error, reload } = useLoad<any>("/dashboard");
  const [pick, setPick] = useState<any>(null);
  const [clock, setClock] = useState("");
  useEffect(() => { const t = setInterval(reload, 30000); return () => clearInterval(t); }, [reload]);
  useEffect(() => {
    const f = () => setClock(new Date().toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Karachi" }));
    f(); const t = setInterval(f, 15000); return () => clearInterval(t);
  }, []);
  if (error) return <Err msg={error} />;
  if (!data) return <Empty>Loading live data…</Empty>;
  const s = data.snapshot, h = data.health;
  const t = s.tasks, a = s.attendance, fin = s.finance, crm = s.crm, ai = s.ai_usage;
  const opParts = Object.entries(s.ai_workforce.by_operational as Record<string, number>).map(([k, v]) => ({ label: k, value: v, tone: OP_TONE[k] || "off" }));
  const operational = s.ai_workforce.by_operational.OPERATIONAL || 0;
  const companiesById: Record<string, any> = Object.fromEntries(s.companies.map((c: any) => [c.id, c]));

  return (
    <div className="grid" style={{ gap: 14 }}>
      <div className="row between">
        <div className="row small muted"><Badge s="CONNECTED" label="LIVE" pulse /> Asia/Karachi · {clock} · refreshed {fmt.ago(s.generated_at)}</div>
        <div className="row small">{s.alerts.filter((x: any) => x.severity === "critical").length > 0
          ? <Badge s="critical" label={`${s.alerts.filter((x: any) => x.severity === "critical").length} critical`} />
          : <Badge s="good" label="No critical alerts" />}</div>
      </div>

      <div className="grid g4">
        <Stat label="Corporate structure" value={`${s.group.companies} · ${s.group.departments}`} detail="companies · departments" />
        <Stat label="Human workforce" value={s.group.people}
          detail={a.working_day ? `${a.present} present · ${a.late} late · ${a.absent} absent · ${a.unmarked} unmarked` : "Sunday — office closed"} />
        <Stat label="AI workforce" value={`${operational}/${s.group.agents}`} state={operational ? "ok" : undefined}
          detail={operational ? "agents operational" : "operational — connect an AI provider"} />
        <Stat label="Open tasks" value={t.open} state={t.overdue ? (t.overdue >= 5 ? "crit" : "warn") : undefined}
          detail={`${t.overdue} overdue · ${t.unassigned} unassigned · ${t.done_today} done today`} />
        <Stat label="Approvals waiting" value={s.approvals_pending} state={s.approvals_pending ? "warn" : undefined} detail={<a href="/work/?tab=approvals">Review queue →</a>} />
        <Stat label="Sales pipeline" value={crm.open_leads} detail={`${fmt.pkr(crm.pipeline_value_pkr)} · ${crm.won_this_month} won this month`} />
        <Stat label="Month net (PKR)" value={fin.has_data ? Math.round(fin.month_net_pkr).toLocaleString("en-PK") : "—"}
          state={fin.has_data ? (fin.month_net_pkr < 0 ? "crit" : "ok") : undefined}
          detail={fin.has_data ? `Revenue ${fmt.pkr(fin.month_revenue_pkr)} · Expenses ${fmt.pkr(fin.month_expense_pkr)}` : "No entries recorded this month"} />
        <Stat label="AI cost this month" value={fmt.usd(ai.cost_month_usd)}
          detail={`${ai.runs_month} runs · ${fmt.num(ai.input_tokens_month + ai.output_tokens_month)} tokens${ai.unpriced_runs ? ` · ${ai.unpriced_runs} unpriced` : ""}`} />
      </div>

      <div className="grid g3">
        <Card title="Company network" className="span2" action={<a className="small" href="/org/">Org map →</a>}>
          <NetworkMap companies={s.companies} onPick={setPick} />
          <div className="faint small">Ring colour = overdue work (green none · amber some · red 3+). Click a company for details.</div>
        </Card>
        <Card title="Strategic alerts">
          {s.alerts.length ? (
            <div className="stack" style={{ gap: 8 }}>
              {s.alerts.map((x: any, i: number) => (
                <div key={i} style={{ borderLeft: `3px solid var(--${x.severity === "critical" ? "red" : x.severity === "warning" ? "amber" : "cyan"})`, paddingLeft: 10 }}>
                  <div style={{ fontWeight: 500 }}>{x.title}</div><div className="muted small">{x.detail}</div>
                </div>
              ))}
            </div>
          ) : <Empty>Nothing needs your attention right now.</Empty>}
        </Card>
      </div>

      <div className="grid g3">
        <Card title="AI workforce status" action={<a className="small" href="/agents/">Factory →</a>}>
          <Donut parts={opParts} label={String(s.group.agents)} sub="AGENTS" />
          <div className="faint small" style={{ marginTop: 8 }}>
            Lifecycle: {Object.entries(s.ai_workforce.by_lifecycle).map(([k, v]) => `${v} ${k}`).join(" · ")} · {s.ai_workforce.coordinators} coordinators
          </div>
        </Card>
        <Card title="Sales pipeline by company" action={<a className="small" href="/crm/">CRM →</a>}>
          <HBars rows={Object.entries(crm.stages_by_company as Record<string, Record<string, number>>).map(([cid, st]) => ({
            label: companiesById[cid]?.name || cid,
            values: [{ v: Object.values(st).reduce((x, y) => x + y, 0), tone: "blue", name: Object.entries(st).map(([k, v]) => `${k}: ${v}`).join(", ") }],
          }))} format={(n) => `${n} leads`} empty="No open leads yet" />
          <div className="faint small" style={{ marginTop: 8 }}>{crm.new_today} new today · {crm.follow_ups_due} follow-ups due · {crm.follow_ups_overdue} overdue · {s.customers.active_30d}/{s.customers.total} customers active (30d)</div>
        </Card>
        <Card title="Revenue & expenses (month)" action={me.permissions.includes("finance.view") ? <a className="small" href="/finance/">Finance →</a> : null}>
          <HBars rows={Object.entries(fin.by_company as Record<string, any>).map(([cid, v]) => ({
            label: companiesById[cid]?.name || cid,
            values: [{ v: v.revenue, tone: "ok", name: "revenue" }, { v: v.expense, tone: "crit", name: "expense" }],
          }))} format={fmt.pkr} empty="No revenue or expense entries this month" />
          <div className="faint small" style={{ marginTop: 8 }}>Receivables {fmt.pkr(fin.outstanding_receivables_pkr)} · {fin.overdue_invoices} invoices overdue</div>
        </Card>
      </div>

      <div className="grid g3">
        <Card title="Department status" className="span2" action={<a className="small" href="/work/?tab=workforce">Workforce intelligence →</a>}>
          <div className="scroll" style={{ maxHeight: 380 }}>
            <table className="tbl">
              <thead><tr><th>Department</th><th>Health</th><th>People</th><th>AI</th><th>Open</th><th>Overdue</th><th>On-time 30d</th></tr></thead>
              <tbody>
                {data.departments.map((d: any) => (
                  <tr key={d.id}>
                    <td><div>{d.name}</div><div className="faint small">{d.company}</div></td>
                    <td><Badge s={d.health} label={d.health === "no_data" ? "no data" : d.health} /></td>
                    <td className="mono">{d.people}</td><td className="mono">{d.agents}</td><td className="mono">{d.open}</td>
                    <td className="mono" style={{ color: d.overdue ? "var(--amber)" : undefined }}>{d.overdue}</td>
                    <td className="mono">{d.on_time_rate == null ? "—" : `${d.on_time_rate}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title="Live activity">
          {data.activity.length ? (
            <div className="feed">
              {data.activity.map((x: any, i: number) => (
                <div key={i}><time>{fmt.ago(x.at)}</time>
                  <span>{x.agent ? "⬡ " : ""}<b style={{ fontWeight: 500 }}>{x.actor || "system"}</b> <span className="muted">{x.action.replace(/\./g, " ")}</span>
                    {x.detail?.name || x.detail?.title ? <span> — {x.detail.name || x.detail.title}</span> : null}</span></div>
              ))}
            </div>
          ) : <Empty>No activity yet.</Empty>}
        </Card>
      </div>

      <div className="grid g3">
        <Card title="Active projects" action={<a className="small" href="/projects/">Projects →</a>}>
          {s.projects.length ? s.projects.map((p: any) => (
            <div key={p.id} style={{ marginBottom: 10 }}>
              <div className="row between"><span>{p.name}</span>{p.needs_attention ? <Badge s="warning" label="attention" /> : <Badge s={p.status} />}</div>
              <div className="bar" style={{ marginTop: 5 }}><i style={{ width: `${p.progress_pct}%` }} /></div>
              <div className="faint small">{p.done}/{p.tasks} tasks · deadline {fmt.date(p.deadline)}{p.why ? ` · ${p.why}` : ""}</div>
            </div>
          )) : <Empty>No active projects.</Empty>}
        </Card>
        <Card title="Overdue tasks" action={<a className="small" href="/work/?overdue=1">All →</a>}>
          {s.overdue_tasks.length ? (
            <div className="stack" style={{ gap: 6 }}>
              {s.overdue_tasks.map((x: any) => (
                <div key={x.id} className="row between small"><span>{x.title}</span><span className="mono" style={{ color: "var(--red)" }}>{fmt.date(x.due_at)}</span></div>
              ))}
            </div>
          ) : <Empty>No overdue tasks.</Empty>}
        </Card>
        <Card title="System health" action={<a className="small" href="/settings/">Settings →</a>}>
          <dl className="kv">
            <dt>Database</dt><dd><Badge s={h.database} /></dd>
            <dt>Queue (Redis)</dt><dd><Badge s={h.redis} /></dd>
            <dt>Background worker</dt><dd><Badge s={h.worker.startsWith("ERROR") ? "ERROR" : h.worker} label={h.worker} /></dd>
            <dt>Cloud sync</dt><dd><Badge s={h.sync} /></dd>
            <dt>Last backup</dt><dd className={h.last_backup ? "" : "faint"}>{h.last_backup ? fmt.dt(h.last_backup) : "never recorded"}</dd>
            <dt>Disk free</dt><dd className="mono" style={{ color: h.disk_free_pct < 15 ? "var(--amber)" : undefined }}>{h.disk_free_pct}%</dd>
            {Object.entries(ai.providers as Record<string, string>).map(([k, v]) => (<Fragment key={k}><dt>{fmt.label(k)}</dt><dd><Badge s={v} /></dd></Fragment>))}
          </dl>
        </Card>
      </div>

      <Drawer open={!!pick} onClose={() => setPick(null)}>
        {pick && (
          <div className="stack">
            <h1>{pick.name}</h1>
            <div className="faint small mono">{pick.code} · {pick.kind}</div>
            <div className="grid g2">
              <Stat label="Departments" value={pick.departments} /><Stat label="People" value={pick.people} />
              <Stat label="AI agents" value={pick.agents} /><Stat label="Open leads" value={pick.open_leads} />
              <Stat label="Open tasks" value={pick.open_tasks} /><Stat label="Overdue" value={pick.overdue_tasks} state={pick.overdue_tasks ? "warn" : undefined} />
            </div>
            <div className="row"><a className="btn" href="/org/">Open org map</a><a className="btn" href="/crm/">CRM</a><a className="btn" href="/agents/">Agents</a></div>
          </div>
        )}
      </Drawer>
    </div>
  );
}

export default function Page() {
  return (
    <Shell title="Global Command Centre" sub="NADIR E-SKILLS (SMC-PRIVATE) LIMITED — whole-group view from live system data">
      <Gate><Centre /></Gate>
    </Shell>
  );
}

function Gate({ children }: { children: React.ReactNode }) {
  const me = useMe();
  useEffect(() => { if (!me.permissions.includes("dashboard.view")) location.replace("/work/"); }, [me]);
  return me.permissions.includes("dashboard.view") ? <>{children}</> : null;
}
