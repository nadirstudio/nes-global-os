"use client";
import { Fragment, useEffect, useState } from "react";
import Shell, { can, useMe } from "@/components/Shell";
import { Badge, Card, Empty, Err, FormModal, Stat, useAction, useLoad } from "@/components/ui";
import { api, fmt } from "@/lib/api";

function AISettings() {
  const me = useMe();
  const prov = useLoad<any[]>("/ai/providers");
  const usage = useLoad<any>("/ai/usage");
  const prices = useLoad<any[]>("/ai/prices");
  const budget = useLoad<any>("/ai/budget");
  const [keyFor, setKeyFor] = useState<any>(null);
  const [priceFor, setPriceFor] = useState<string | null>(null);
  const [editBudget, setEditBudget] = useState(false);
  const [testModel, setTestModel] = useState<Record<string, string>>({ anthropic: "claude-haiku-5-5" });
  const act = useAction();
  const [testRes, setTestRes] = useState<any>(null);
  const admin = can(me, "ai.settings");
  const u = usage.data;
  const models = [...new Set([...(u?.by_model || []).map((m: any) => m.model), "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"])];
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="note">
        Your <b>Claude.ai subscription</b> (and Claude Code) is for building and maintaining this codebase. Agents running in the background need an <b>Anthropic API key</b> from console.anthropic.com, billed separately per token.
        Keys are encrypted in the database (or set as server environment variables) and are never sent to the browser.
      </div>
      <Card title="AI providers">
        <table className="tbl"><thead><tr><th>Provider</th><th>Status</th><th>Key</th><th>Last check</th><th /></tr></thead><tbody>
          {prov.data?.map((p) => (
            <tr key={p.provider}><td>{p.label}{p.base_url && <div className="faint small mono">{p.base_url}</div>}</td><td><Badge s={p.status} />{p.last_error && <div className="faint small">{p.last_error}</div>}</td>
              <td className="small">{p.key_source === "none" ? "—" : `${p.key_hint || "set"} (${p.key_source})`}</td><td className="small">{fmt.dt(p.last_checked_at)}</td>
              <td>{admin && (
                <div className="row" style={{ flexWrap: "nowrap" }}>
                  <button className="btn sm" onClick={() => setKeyFor(p)}>{p.key_source === "none" ? "Add key" : "Change"}</button>
                  {p.key_source !== "none" && <>
                    <input className="mono" style={{ width: 150, padding: "3px 6px" }} placeholder="model to test" value={testModel[p.provider] || ""} onChange={(e) => setTestModel({ ...testModel, [p.provider]: e.target.value })} />
                    <button className="btn sm" disabled={act.busy || !testModel[p.provider]} onClick={() => act.run(async () => { setTestRes(await api(`/ai/providers/${p.provider}/test`, { body: { model: testModel[p.provider] } })); prov.reload(); })}>Test</button>
                    {p.key_source === "admin settings" && <button className="btn sm danger" onClick={() => confirm("Remove this key?") && act.run(async () => { await api(`/ai/providers/${p.provider}`, { method: "DELETE" }); prov.reload(); })}>Remove</button>}
                  </>}
                </div>)}</td></tr>
          ))}</tbody></table>
        <Err msg={act.err} />
        {testRes && <div className={testRes.ok ? "note" : "err"} style={{ marginTop: 8 }}>{testRes.ok ? `Connected — model replied “${testRes.reply}” (${testRes.tokens} tokens)` : testRes.error}</div>}
      </Card>
      <div className="grid g4">
        <Stat label="Spend this month" value={fmt.usd(u?.month_spend_usd)} detail={budget.data?.monthly_limit_usd != null ? `limit $${budget.data.monthly_limit_usd}` : "no monthly limit"} />
        <Stat label="Spend today" value={fmt.usd(u?.today_spend_usd)} detail={budget.data?.daily_limit_usd != null ? `limit $${budget.data.daily_limit_usd}` : "no daily limit"} />
        <Stat label="Alert threshold" value={`${budget.data?.alert_pct ?? 80}%`} detail={admin ? <a onClick={() => setEditBudget(true)} style={{ cursor: "pointer" }}>Edit budgets →</a> : undefined} />
        <Stat label="Unpriced models" value={(u?.by_model || []).filter((m: any) => !m.fully_priced).length} detail="set prices for accurate costs" />
      </div>
      {u?.alerts?.map((a: any, i: number) => <div key={i} className={a.severity === "critical" ? "err" : "note"}>{a.title}</div>)}
      <div className="grid g2">
        <Card title="Usage by agent (30 days)">
          {u?.by_agent?.length ? <table className="tbl"><thead><tr><th>Agent</th><th>Runs</th><th>Tokens</th><th>Cost</th><th>Budget</th></tr></thead><tbody>
            {u.by_agent.map((a: any) => <tr key={a.agent_id}><td>{a.name}{a.non_success ? <span className="faint small"> · {a.non_success} not ok</span> : null}</td><td className="mono">{a.runs}</td>
              <td className="mono small">{fmt.num(a.input_tokens)} in / {fmt.num(a.output_tokens)} out</td><td className="mono">{fmt.usd(a.cost_usd)}</td><td className="mono small">{a.monthly_budget != null ? `$${a.monthly_budget}` : "—"}</td></tr>)}
          </tbody></table> : <Empty>No AI usage yet.</Empty>}
        </Card>
        <Card title="Model prices (USD per million tokens)" action={<span className="faint small">enter your current contract prices</span>}>
          <table className="tbl"><thead><tr><th>Model</th><th>Input</th><th>Output</th><th /></tr></thead><tbody>
            {models.map((m) => { const p = prices.data?.find((x) => x.model === m); return (
              <tr key={m}><td className="mono small">{m}</td><td className="mono">{p ? `$${p.input_per_mtok}` : <span className="faint">not set</span>}</td><td className="mono">{p ? `$${p.output_per_mtok}` : "—"}</td>
                <td>{admin && <button className="btn sm" onClick={() => setPriceFor(m)}>Set</button>}</td></tr>); })}
          </tbody></table>
        </Card>
      </div>
      {keyFor && (
        <FormModal title={`${keyFor.label} credentials`} onClose={() => setKeyFor(null)} submitLabel="Save securely"
          fields={[{ name: "api_key", label: "API key", type: "password", required: keyFor.key_source === "none", help: "Stored encrypted. Leave blank to keep the current key." },
            { name: "base_url", label: "Base URL (optional)", help: keyFor.provider === "openai_compatible" ? "Required, e.g. https://your-endpoint" : "Leave empty for the official endpoint" },
            { name: "enabled", label: "Enabled", type: "checkbox" }]}
          initial={{ enabled: true, base_url: keyFor.base_url }}
          onSubmit={async (v) => { if (!v.api_key) delete v.api_key; await api(`/ai/providers/${keyFor.provider}`, { method: "PUT", body: v }); prov.reload(); }} />
      )}
      {priceFor && (
        <FormModal title={`Price for ${priceFor}`} onClose={() => setPriceFor(null)}
          fields={[{ name: "provider", label: "Provider", type: "select", required: true, options: ["anthropic", "openai", "gemini", "openai_compatible"].map((x) => ({ value: x, label: x })) },
            { name: "input_per_mtok", label: "Input $/MTok", type: "number", required: true }, { name: "output_per_mtok", label: "Output $/MTok", type: "number", required: true }]}
          initial={prices.data?.find((x) => x.model === priceFor) || { provider: priceFor.startsWith("claude") ? "anthropic" : "" }}
          onSubmit={async (v) => { await api(`/ai/prices/${encodeURIComponent(priceFor)}`, { method: "PUT", body: v }); prices.reload(); usage.reload(); }} />
      )}
      {editBudget && (
        <FormModal title="AI budgets" onClose={() => setEditBudget(false)} initial={budget.data || {}}
          fields={[{ name: "monthly_limit_usd", label: "Monthly limit (USD)", type: "number", help: "Empty = no limit" },
            { name: "daily_limit_usd", label: "Daily limit (USD)", type: "number" }, { name: "alert_pct", label: "Alert at % of limit", type: "number", required: true }]}
          onSubmit={async (v) => { await api("/ai/budget", { method: "PUT", body: v }); budget.reload(); usage.reload(); }} />
      )}
    </div>
  );
}

function System() {
  const me = useMe();
  const integ = useLoad<any[]>(can(me, "integrations.view") ? "/integrations" : null);
  const ops = useLoad<any>("/settings/daily-ops");
  const [edit, setEdit] = useState(false);
  return (
    <div className="stack" style={{ gap: 14 }}>
      <Card title="Integrations" action={<span className="faint small">CONNECTED is only shown after a verified connection</span>}>
        <table className="tbl"><tbody>{integ.data?.map((i) => (
          <tr key={i.key}><td>{i.name}</td><td><Badge s={i.status} /></td><td className="small muted">{i.detail || ""}</td>
            <td>{can(me, "integrations.manage") && i.status !== "NOT CONNECTED" && <button className="btn sm" onClick={async () => { await api(`/integrations/${i.key}`, { method: "PATCH", body: { status: "NOT CONNECTED" } }); integ.reload(); }}>Disconnect</button>}</td></tr>
        ))}</tbody></table>
        <div className="faint small" style={{ marginTop: 8 }}>Google Workspace (OAuth 2.0) and WhatsApp Cloud API connectors are scheduled in the roadmap phases 11–12; see INTEGRATION_STATUS.md for what credentials each needs.</div>
      </Card>
      {ops.data && (
        <Card title="Daily operations schedule (Asia/Karachi)" action={can(me, "company.manage") && <button className="btn sm" onClick={() => setEdit(true)}>Edit</button>}>
          <dl className="kv">
            <dt>Working days</dt><dd>{ops.data.workdays.map((d: number) => ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d]).join(", ")}</dd>
            <dt>Office hours</dt><dd>{ops.data.office_start} – {ops.data.office_end}</dd>
            {Object.entries(ops.data.jobs).map(([k, v]) => <Fragment key={k}><dt>{fmt.label(k)}</dt><dd className="mono">{k === "agent_queue_minutes" ? `every ${v} min (all days)` : String(v)}</dd></Fragment>)}
          </dl>
        </Card>
      )}
      {edit && (
        <FormModal title="Daily operations" onClose={() => setEdit(false)} initial={ops.data.jobs}
          fields={Object.keys(ops.data.jobs).map((k) => ({ name: k, label: fmt.label(k), type: k === "agent_queue_minutes" ? "number" as const : "text" as const, help: k === "agent_queue_minutes" ? undefined : "HH:MM" }))}
          onSubmit={async (v) => { await api("/settings/daily-ops", { method: "PUT", body: { ...ops.data, jobs: v } }); ops.reload(); }} />
      )}
    </div>
  );
}

function Security() {
  const me = useMe();
  const [setup, setSetup] = useState<any>(null);
  const [code, setCode] = useState("");
  const [pw, setPw] = useState(false);
  const act = useAction();
  const [done, setDone] = useState<string | null>(null);
  return (
    <div className="stack" style={{ gap: 14 }}>
      <Card title="Multi-factor authentication">
        {me.user.mfa_enabled ? <div className="row"><Badge s="CONNECTED" label="MFA enabled" />
          <button className="btn sm" onClick={() => { const c = prompt("Authenticator code"); const p = c && prompt("Your password"); if (c && p) act.run(async () => { await api("/auth/mfa/disable", { body: { code: c, password: p } }); location.reload(); }); }}>Disable</button></div>
          : !setup ? <button className="btn primary" onClick={() => act.run(async () => setSetup(await api("/auth/mfa/setup", { method: "POST" })))}>Set up authenticator app</button>
            : (<div className="stack">
              <div className="small">In Google Authenticator / Microsoft Authenticator, add an account with this key:</div>
              <div className="mono" style={{ fontSize: 16, letterSpacing: 2 }}>{setup.secret}</div>
              <div className="faint small" style={{ wordBreak: "break-all" }}>{setup.otpauth_uri}</div>
              <div className="row" style={{ flexWrap: "nowrap" }}><input placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value)} />
                <button className="btn primary" onClick={() => act.run(async () => { await api("/auth/mfa/enable", { body: { code } }); setDone("MFA enabled."); setTimeout(() => location.reload(), 800); })}>Verify & enable</button></div>
            </div>)}
        <Err msg={act.err} />{done && <div className="note">{done}</div>}
      </Card>
      <Card title="Password & sessions">
        <div className="row">
          <button className="btn" onClick={() => setPw(true)}>Change password</button>
          <button className="btn" onClick={() => act.run(async () => { await api("/auth/logout-all", { method: "POST" }); location.href = "/login/"; })}>Sign out of all devices</button>
        </div>
      </Card>
      {pw && <FormModal title="Change password" onClose={() => setPw(false)}
        fields={[{ name: "current_password", label: "Current password", type: "password", required: true }, { name: "new_password", label: "New password", type: "password", required: true, help: "10+ characters, 3 of: upper, lower, digit, symbol" }]}
        onSubmit={async (v) => { await api("/auth/change-password", { body: v }); location.href = "/login/"; }} />}
    </div>
  );
}

function Audit() {
  const { data, error } = useLoad<any[]>("/audit?limit=300");
  return (
    <Card title="Audit log (latest 300)">
      <Err msg={error} />
      <div className="scroll" style={{ maxHeight: 640 }}><table className="tbl"><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Entity</th><th>Detail</th><th>IP</th></tr></thead><tbody>
        {data?.map((a) => <tr key={a.id}><td className="small mono">{fmt.dt(a.at)}</td><td className="small">{a.actor_agent_id ? "⬡ " : ""}{a.actor_label}</td><td className="small">{a.action}</td>
          <td className="small faint">{a.entity}</td><td className="small faint mono" style={{ maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis" }}>{JSON.stringify(a.detail)}</td><td className="small faint mono">{a.ip}</td></tr>)}
      </tbody></table></div>
    </Card>
  );
}

function Settings() {
  const me = useMe();
  const tabs = [...(can(me, "ai.usage.view") ? [["ai", "AI & costs"]] : []), ...(can(me, "dashboard.view") ? [["system", "Integrations & schedule"]] : []), ["security", "My security"], ...(can(me, "audit.view") ? [["audit", "Audit log"]] : [])];
  const [tab, setTab] = useState(tabs[0][0]);
  useEffect(() => { setTab(tabs[0][0]); }, [me.user.role]); // eslint-disable-line
  return (
    <>
      <div className="tabs">{tabs.map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "ai" && <AISettings />}{tab === "system" && <System />}{tab === "security" && <Security />}{tab === "audit" && <Audit />}
    </>
  );
}

export default function Page() {
  return <Shell title="Settings & System" sub="AI providers and budgets · integrations · daily operations · security · audit"><Settings /></Shell>;
}
