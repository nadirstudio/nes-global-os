import { useState } from "react";
import { useApp } from "../App";
import { api, fmt } from "../api";
import { Card, Empty, Err, Header, Loading, useLoad } from "../ui";

export function News() {
  const app = useApp();
  const { data, error, setData } = useLoad<any[]>("/mobile/news");
  const [open, setOpen] = useState<string | null>(null);
  const toggle = async (n: any) => {
    setOpen(open === n.id ? null : n.id);
    if (!n.read) {
      setData((data || []).map((x) => (x.id === n.id ? { ...x, read: true } : x)));
      try { await api(`/mobile/news/${n.id}/read`, { method: "POST" }); app.refreshCounts(); } catch { /* ignore */ }
    }
  };
  return (
    <div className="screen">
      <Header title="Company news" back={app.back} />
      <div className="content">
        <Err msg={error} />
        {!data ? <Loading /> : data.length === 0 ? <Card><Empty icon="📢">No announcements yet.</Empty></Card> : data.map((n) => (
          <Card key={n.id} onClick={() => toggle(n)} className={n.priority === "urgent" ? "urgent" : ""}>
            <div className="stack" style={{ gap: 6 }}>
              <div className="row between">
                <div className="row" style={{ gap: 6 }}>
                  {n.pinned && <span title="Pinned">📌</span>}
                  {n.priority === "urgent" && <span className="chip bad">Urgent</span>}
                  {!n.read && <span className="chip info">New</span>}
                </div>
                <span className="tiny muted">{fmt.ago(n.created_at)}</span>
              </div>
              <div style={{ fontWeight: n.read ? 600 : 750, fontSize: 16 }}>{n.title}</div>
              <div className={open === n.id ? "pre" : "small muted ellipsis"}>{n.body}</div>
              <div className="tiny muted">{n.audience}{n.author ? ` · ${n.author}` : ""}</div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
