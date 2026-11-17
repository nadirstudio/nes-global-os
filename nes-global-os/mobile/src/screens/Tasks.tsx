import { useEffect, useState } from "react";
import { useApp } from "../App";
import { api, fmt } from "../api";
import { Card, Chip, Empty, Err, Field, Header, Loading, Segmented, useAction, useLoad } from "../ui";

export function Tasks() {
  const app = useApp();
  const [view, setView] = useState("open");
  const path = view === "team" ? "/tasks?status=open" : view === "done" ? "/tasks?mine=true&status=done" : "/tasks?mine=true&status=open";
  const { data, error, loading, reload } = useLoad<any[]>(path, [view]);
  const opts = [{ value: "open", label: "To do" }, { value: "done", label: "Done" }, ...(app.me.is_leader ? [{ value: "team", label: "Team" }] : [])];
  return (
    <div className="screen">
      <Header title="Tasks" right={<button className="icon-btn" onClick={() => reload()} aria-label="Refresh">↻</button>} />
      <div className="content">
        <Segmented value={view} onChange={setView} options={opts} />
        <Err msg={error} />
        {loading && !data ? <Loading /> : data?.length ? (
          <div className="list">
            {data.map((t) => (
              <div key={t.id} className="li tap" onClick={() => app.push({ name: "task", params: { id: t.id } })}>
                <div className="grow">
                  <div className="ellipsis" style={{ fontWeight: 600 }}>{t.priority === "urgent" ? "🔴 " : t.priority === "high" ? "🟠 " : ""}{t.title}</div>
                  <div className="tiny muted">{t.due_at ? `Due ${fmt.date(t.due_at)}` : "No due date"} · {t.estimated_hours}h</div>
                </div>
                <Chip s={t.overdue ? "overdue" : t.status} label={t.overdue ? "overdue" : undefined} />
                <span className="chev">›</span>
              </div>
            ))}
          </div>
        ) : <Card><Empty icon="☑">{view === "done" ? "Nothing completed in this list yet." : "No open tasks. Nice work!"}</Empty></Card>}
      </div>
    </div>
  );
}

const STEPS = [
  { value: "todo", label: "To do" }, { value: "in_progress", label: "Doing" }, { value: "blocked", label: "Blocked" },
  { value: "done", label: "Done" },
];

export function TaskDetail({ id }: { id: string }) {
  const app = useApp();
  const { data: t, error, setData } = useLoad<any>(`/tasks/${id}`, [id]);
  const [result, setResult] = useState("");
  const act = useAction();
  useEffect(() => { if (t) setResult(t.result || ""); }, [t?.id]); // eslint-disable-line
  const patch = (body: any) => act.run(async () => {
    const r = await api<any>(`/tasks/${id}`, { method: "PATCH", body });
    setData({ ...t, ...r, overdue: false });
  });
  return (
    <div className="screen">
      <Header title="Task" back={app.back} />
      <div className="content">
        <Err msg={error || act.err} />
        {!t ? <Loading /> : (
          <>
            <Card>
              <div className="stack" style={{ gap: 8 }}>
                <h2>{t.title}</h2>
                <div className="row wrap"><Chip s={t.overdue ? "overdue" : t.status} label={t.overdue ? "overdue" : undefined} /><Chip s="todo" label={`${t.priority} priority`} /><Chip s="todo" label={t.complexity} /></div>
                <div className="small muted">
                  {t.due_at ? `Due ${fmt.date(t.due_at)} ${fmt.time(t.due_at)}` : "No due date"} · {t.estimated_hours}h estimated
                  {t.project ? ` · ${t.project}` : ""}
                </div>
                {t.reviewer && <div className="small muted">Reviewer: {t.reviewer}</div>}
                {t.description && <div className="pre">{t.description}</div>}
              </div>
            </Card>
            <div className="section-title"><span>Update status</span></div>
            <Segmented value={t.status === "review" ? "done" : t.status} onChange={(v) => patch({ status: v })} options={STEPS} />
            {t.status === "review" && <div className="note small">Sent to your reviewer for approval.</div>}
            <Field label="Result / notes" hint="What you did, links, or what's blocking you.">
              <textarea value={result} onChange={(e) => setResult(e.target.value)} />
            </Field>
            <button className="btn primary block" disabled={act.busy || result === (t.result || "")} onClick={() => patch({ result })}>Save notes</button>
            {t.can_review && t.status === "review" && (
              <Card>
                <h3>Review</h3>
                <div className="row">
                  <button className="btn green grow" onClick={() => patch({ status: "done" })}>Approve</button>
                  <button className="btn grow" onClick={() => patch({ status: "in_progress" })}>Send back</button>
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}
