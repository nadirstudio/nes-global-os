import { useState } from "react";
import { useApp } from "../App";
import { api, fileBase, fmt } from "../api";
import { openUrl } from "../native";
import { Card, Empty, Err, Header, Loading, Segmented, useAction, useLoad } from "../ui";

const CATS = [
  { value: "", label: "All" }, { value: "policy", label: "Policies" }, { value: "sop", label: "SOPs" },
  { value: "handbook", label: "Handbook" }, { value: "training", label: "Training" }, { value: "contract", label: "Contracts" },
  { value: "form", label: "Forms" },
];
const ICON: Record<string, string> = { policy: "📘", sop: "🧭", handbook: "📗", training: "🎓", contract: "📝", form: "🗂" };

export function Docs() {
  const app = useApp();
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const { data, error } = useLoad<any[]>(`/mobile/documents${cat ? `?category=${cat}` : ""}`, [cat]);
  const list = (data || []).filter((d) => !q || `${d.title} ${d.excerpt}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="screen">
      <Header title="Documents" back={app.back} />
      <div className="content">
        <div className="search"><input placeholder="Search documents…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Segmented value={cat} onChange={setCat} options={CATS} />
        <Err msg={error} />
        {!data ? <Loading /> : list.length === 0 ? <Card><Empty icon="📄">No documents here yet.</Empty></Card> : (
          <div className="list">
            {list.map((d) => (
              <div key={d.id} className="li tap" onClick={() => app.push({ name: "doc", params: { id: d.id } })}>
                <div className="avatar" style={{ width: 40, height: 40, background: "#e8efff", fontSize: 20 }}>{ICON[d.category] || "📄"}</div>
                <div className="grow"><div className="ellipsis" style={{ fontWeight: 600 }}>{d.title}</div>
                  <div className="tiny muted">{fmt.label(d.category)}{d.personal ? " · personal" : ""} · updated {fmt.date(d.updated_at)}</div></div>
                <span className="chev">›</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function DocView({ id }: { id: string }) {
  const app = useApp();
  const { data: d, error } = useLoad<any>(`/mobile/documents/${id}`, [id]);
  const act = useAction();
  const openFile = () => act.run(async () => {
    const r = await api<any>(`/mobile/documents/${id}/link`, { method: "POST" });
    await openUrl(fileBase() + r.path);
  });
  return (
    <div className="screen">
      <Header title="Document" back={app.back} />
      <div className="content">
        <Err msg={error || act.err} />
        {!d ? <Loading /> : (
          <>
            <Card>
              <div className="stack" style={{ gap: 6 }}>
                <h2>{d.title}</h2>
                <div className="tiny muted">{fmt.label(d.category)} · version {d.version} · updated {fmt.date(d.updated_at)}</div>
                {d.has_file && <button className="btn primary block" disabled={act.busy} onClick={openFile}>📎 Open {d.file_name || "file"}</button>}
              </div>
            </Card>
            {d.body_text ? <Card><div className="pre small">{d.body_text}</div></Card> : !d.has_file && <Card><Empty>No content.</Empty></Card>}
            <button className="btn block" onClick={() => app.push({ name: "assistant", params: { q: `Summarise “${d.title}”` } })}>🤖 Ask about this document</button>
          </>
        )}
      </div>
    </div>
  );
}
