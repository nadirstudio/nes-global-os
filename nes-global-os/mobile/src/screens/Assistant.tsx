import { useEffect, useRef, useState } from "react";
import { useApp } from "../App";
import { api } from "../api";
import { Header } from "../ui";

const SUGGEST = [
  "How many casual leaves do I have left?", "What is the travel reimbursement policy?", "What are my open tasks?",
  "What is my attendance this month?", "Who is my manager?", "What is my shift today?",
];

type Msg = { q: string; a?: string; source?: string; sources?: { id: string; title: string }[]; err?: string };

export function Assistant({ initial }: { initial?: string }) {
  const app = useApp();
  const [log, setLog] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const asked = useRef(false);

  const ask = async (q: string) => {
    q = q.trim();
    if (!q || busy) return;
    setText("");
    setBusy(true);
    setLog((l) => [...l, { q }]);
    try {
      const r = await api<any>("/mobile/assistant", { body: { question: q } });
      setLog((l) => [...l.slice(0, -1), { q, a: r.answer, source: r.source, sources: r.sources }]);
    } catch (e) {
      setLog((l) => [...l.slice(0, -1), { q, err: (e as Error).message }]);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => { if (initial && !asked.current) { asked.current = true; ask(initial); } }, [initial]); // eslint-disable-line
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [log]);

  return (
    <div className="chat" style={{ height: "100vh" }}>
      <Header title="Ask HR" back={app.back} />
      <div className="msgs">
        <div className="bubble"><div className="who">NES Help Desk</div>Hi {app.me.name.split(" ")[0] || "there"}! Ask me about your leave, tasks, attendance or company policies. I only use your own records and published company documents.</div>
        {log.length === 0 && (
          <div className="stack" style={{ gap: 8, marginTop: 6 }}>
            {SUGGEST.map((s) => <button key={s} className="btn sm" style={{ justifyContent: "flex-start" }} onClick={() => ask(s)}>{s}</button>)}
          </div>
        )}
        {log.map((m, i) => (
          <div key={i} style={{ display: "contents" }}>
            <div className="bubble mine">{m.q}</div>
            <div className="bubble">
              <div className="who">NES Help Desk{m.source === "ai" ? " · AI" : ""}</div>
              {m.err ? <span style={{ color: "var(--red)" }}>{m.err}</span> : m.a ?? <span className="muted">Thinking…</span>}
              {!!m.sources?.length && (
                <div className="tiny" style={{ marginTop: 6 }}>Sources: {m.sources.map((s, j) => (
                  <a key={s.id} onClick={() => app.push({ name: "doc", params: { id: s.id } })}>{j ? ", " : ""}{s.title}</a>
                ))}</div>
              )}
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>
      <div className="composer">
        <textarea rows={1} value={text} placeholder="Type your question" maxLength={1000} onChange={(e) => setText(e.target.value)} />
        <button className="send" disabled={busy || !text.trim()} onClick={() => ask(text)} aria-label="Ask">➤</button>
      </div>
    </div>
  );
}
