import { useMemo, useState } from "react";
import { useApp } from "../App";
import { api } from "../api";
import { telLink, waLink } from "../native";
import { calls } from "../calls";
import { Avatar, Card, Empty, Err, Header, Loading, useAction, useLoad } from "../ui";

export function People() {
  const app = useApp();
  const { data, error } = useLoad<any[]>("/mobile/directory");
  const [q, setQ] = useState("");
  const list = useMemo(() => {
    const s = q.toLowerCase();
    return (data || []).filter((p) => !s || `${p.name} ${p.designation || ""} ${p.company || ""} ${p.department || ""} ${p.phone || ""}`.toLowerCase().includes(s));
  }, [data, q]);
  const groups = useMemo(() => {
    const g: Record<string, any[]> = {};
    for (const p of list) (g[p.company || "Other"] ||= []).push(p);
    return Object.entries(g).sort(([a], [b]) => a.localeCompare(b));
  }, [list]);
  return (
    <div className="screen">
      <Header title="People" />
      <div className="content">
        <div className="search"><input placeholder="Search name, role, branch, phone…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Err msg={error} />
        {!data ? <Loading /> : list.length === 0 ? <Card><Empty icon="👥">No one matches “{q}”.</Empty></Card> : groups.map(([company, people]) => (
          <div key={company} className="stack" style={{ gap: 8 }}>
            <div className="section-title"><span>{company}</span><span>{people.length}</span></div>
            <div className="list">
              {people.map((p) => (
                <div key={p.id} className="li tap" onClick={() => app.push({ name: "person", params: { person: p } })}>
                  <div className="ava-wrap"><Avatar name={p.name} />{p.online && <span className="online-dot" title="Online" />}</div>
                  <div className="grow"><div className="ellipsis" style={{ fontWeight: 600 }}>{p.name}{p.id === app.me.person_id ? " (you)" : ""}</div>
                    <div className="tiny muted ellipsis">{[p.designation, p.department].filter(Boolean).join(" · ") || "—"}</div></div>
                  {p.user_id && p.id !== app.me.person_id && (
                    <button className="btn sm" aria-label={`Free call ${p.name}`}
                      onClick={(e) => { e.stopPropagation(); calls.callUser(p.user_id, p.name, "audio").catch((err) => window.alert(err.message)); }}>📞</button>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PersonCard({ person: p }: { person: any }) {
  const app = useApp();
  const act = useAction();
  const message = () => act.run(async () => {
    const ch = await api<any>("/mobile/chat/direct", { body: { user_id: p.user_id } });
    app.back();
    app.push({ name: "conversation", params: { id: ch.id, title: ch.title } });
  });
  return (
    <div className="screen">
      <Header title="Contact" back={app.back} />
      <div className="content">
        <Card>
          <div className="stack" style={{ alignItems: "center", textAlign: "center", gap: 6 }}>
            <div className="ava-wrap"><Avatar name={p.name} size={76} />{p.online && <span className="online-dot" style={{ width: 16, height: 16 }} />}</div>
            <h2>{p.name}</h2>
            <div className="muted">{p.designation || "—"}</div>
            <div className="small muted">{[p.department, p.company].filter(Boolean).join(" · ")}</div>
            <div className="tiny muted">ID {p.code}</div>
          </div>
        </Card>
        {p.user_id && p.id !== app.me.person_id && (
          <div className="row">
            <button className="btn primary grow" onClick={() => act.run(() => calls.callUser(p.user_id, p.name, "audio"))}>📞 Free call</button>
            <button className="btn primary grow" onClick={() => act.run(() => calls.callUser(p.user_id, p.name, "video"))}>🎥 Video call</button>
          </div>
        )}
        <div className="row">
          <button className="btn grow" disabled={!p.user_id || act.busy || p.id === app.me.person_id} onClick={message}>💬 Message</button>
          <a className="btn grow" href={telLink(p.phone)} aria-disabled={!p.phone}>📱 Phone (SIM)</a>
        </div>
        <div className="row">
          <a className="btn grow" href={p.email ? `mailto:${p.email}` : undefined} aria-disabled={!p.email}>✉️ Email</a>
          <a className="btn grow" href={waLink(p.phone)} target="_blank" rel="noreferrer" aria-disabled={!p.phone}>🟢 WhatsApp</a>
        </div>
        {p.user_id && <div className="tiny muted">{p.online ? "🟢 Online in NES Team now." : "Offline right now — if you call, they'll see a missed call."} Free calls use Wi-Fi or Tailscale, not your SIM.</div>}
        <Err msg={act.err} />
        <div className="list">
          <div className="li"><span className="muted small" style={{ width: 70 }}>Phone</span><span className="grow">{p.phone || "—"}</span></div>
          <div className="li"><span className="muted small" style={{ width: 70 }}>Email</span><span className="grow ellipsis">{p.email || "—"}</span></div>
        </div>
        {!p.user_id && <div className="note small">{p.name.split(" ")[0]} doesn't have an app login yet, so in-app messages aren't available.</div>}
      </div>
    </div>
  );
}
