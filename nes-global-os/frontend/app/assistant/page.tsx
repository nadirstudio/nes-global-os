"use client";
import { useState } from "react";
import Shell, { can, useMe } from "@/components/Shell";
import { Badge, Card, Empty, Err, useAction, useLoad } from "@/components/ui";
import { api, fmt } from "@/lib/api";

const ASK = [
  "What is happening across my entire group today?", "Which employees have pending tasks?", "Which department is underperforming?",
  "Which employees have unused capacity?", "Which projects require my attention?", "Identify the most profitable services.",
  "Prepare my management meeting.", "Which business opportunities should I explore?", "Prepare a hiring plan.", "Develop an expansion strategy.",
];
const REPORTS = [["ceo_briefing", "Daily briefing"], ["progress_report", "Progress report"], ["daily_close", "Daily close"],
  ["task_recommendations", "Task recommendations"], ["weekly", "Weekly report"], ["monthly", "Monthly review"]];

type Msg = { q: string; answer?: string; source?: string; status?: any; error?: string };

function Assistant() {
  const me = useMe();
  const [q, setQ] = useState("");
  const [log, setLog] = useState<Msg[]>([]);
  const act = useAction();
  const reports = useLoad<any[]>(can(me, "reports.view") ? "/reports" : null);
  const [report, setReport] = useState<any>(null);
  const ask = async (question: string) => {
    if (!question.trim()) return;
    setQ("");
    setLog((l) => [{ q: question }, ...l]);
    try {
      const r: any = await api("/assistant/ask", { body: { question } });
      setLog((l) => [{ q: question, answer: r.answer, source: r.source, status: r.assistant_status }, ...l.slice(1)]);
    } catch (e) {
      setLog((l) => [{ q: question, error: (e as Error).message }, ...l.slice(1)]);
    }
  };
  const status = log.find((m) => m.status)?.status;
  return (
    <div className="grid g3">
      <div className="span2 stack" style={{ gap: 14 }}>
        <Card title="Ask your Chief of Staff" action={status && <Badge s={status.operational} label={`AI: ${status.operational}`} />}>
          <form className="row" style={{ flexWrap: "nowrap" }} onSubmit={(e) => { e.preventDefault(); ask(q); }}>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask anything about your companies, people, agents, sales or finances…" />
            <button className="btn primary">Ask</button>
          </form>
          <div className="row" style={{ marginTop: 10 }}>{ASK.map((x) => <button key={x} className="btn sm ghost" onClick={() => ask(x)}>{x}</button>)}</div>
          <div className="faint small" style={{ marginTop: 8 }}>
            Answers are computed from live system data first. When the Executive Assistant agent is active and Claude is connected, it writes the narrative on top of those verified facts — it never invents figures or claims actions it didn&apos;t take.
          </div>
        </Card>
        {log.length ? log.map((m, i) => (
          <Card key={i} title={m.q} action={m.source && <Badge s={m.source === "data-only" ? "info" : "ok"} label={m.source === "data-only" ? "verified data" : m.source.replace("ai:", "Claude · ")} />}>
            {m.error ? <Err msg={m.error} /> : m.answer ? <pre className="out">{m.answer}</pre> : <div className="muted">Thinking…</div>}
            {m.source === "data-only" && m.status && m.status.operational !== "OPERATIONAL" && (
              <div className="note small" style={{ marginTop: 8 }}>AI narrative unavailable — {m.status.reason}. Connect Claude in Settings → AI, then test and activate the Executive Assistant agent.</div>
            )}
          </Card>
        )) : null}
      </div>
      {can(me, "reports.view") && (
        <div className="stack" style={{ gap: 14 }}>
          <Card title="Reports">
            <div className="row">{REPORTS.map(([k, l]) => (
              <button key={k} className="btn sm" disabled={act.busy} onClick={() => act.run(async () => { const r = await api("/reports/generate", { body: { kind: k } }); setReport(r); reports.reload(); })}>{l}</button>
            ))}</div>
            <Err msg={act.err} />
            <div className="faint small" style={{ marginTop: 8 }}>Generated automatically Mon–Sat: briefing 08:45, recommendations 09:15, progress 16:30, close 17:00; weekly on Saturday; monthly on the last working day.</div>
          </Card>
          <Card title="Report history">
            {reports.data?.length ? reports.data.map((r) => (
              <div key={r.id} className="row between small" style={{ padding: "6px 0", borderBottom: "1px dashed var(--line)", cursor: "pointer" }}
                onClick={async () => setReport(await api(`/reports/${r.id}`))}>
                <span>{r.title}</span><span className="faint mono">{fmt.dt(r.generated_at)}</span>
              </div>
            )) : <Empty>No reports yet.</Empty>}
          </Card>
          {report && (
            <Card title={report.title} action={<Badge s={report.narrative_source === "data-only" ? "info" : "ok"} label={report.narrative_source} />}>
              <div className="faint small">{report.period_start} → {report.period_end} · {fmt.dt(report.generated_at)}</div>
              <pre className="out">{report.narrative}</pre>
              <button className="btn sm" onClick={() => {
                const w = window.open("", "_blank"); if (!w) return;
                w.document.write(`<title>${report.title}</title><pre style="font:14px/1.6 system-ui;white-space:pre-wrap;max-width:780px;margin:40px auto">${report.narrative.replace(/</g, "&lt;")}</pre>`);
                w.document.close(); w.print();
              }}>Print / save PDF</button>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return <Shell title="Executive AI" sub="Chief of Staff · briefings · reports · decisions — grounded in your real data"><Assistant /></Shell>;
}
