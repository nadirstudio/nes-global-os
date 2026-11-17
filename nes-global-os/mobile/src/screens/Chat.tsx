import { useEffect, useRef, useState } from "react";
import { useApp } from "../App";
import { api, fmt } from "../api";
import { calls, fmtDur } from "../calls";
import { Avatar, Card, Empty, Err, Header, Loading, Segmented, useLoad } from "../ui";

const KIND_ICON: Record<string, string> = { all: "🏢", company: "🏬", department: "👥", group: "👥" };

export function ChatList() {
  const app = useApp();
  const [view, setView] = useState<"chats" | "calls">(app.counts.missed_calls > 0 ? "calls" : "chats");
  const { data, error, reload } = useLoad<any[]>("/mobile/chat/channels");
  useEffect(() => { const t = setInterval(() => reload(true), 8000); return () => clearInterval(t); }, [reload]);
  return (
    <div className="screen">
      <Header title="Chat & calls" right={<button className="icon-btn" onClick={() => app.setTab("people")} aria-label="New message">✎</button>} />
      <div className="content">
        <Segmented value={view} onChange={setView} options={[{ value: "chats", label: `Chats${app.counts.unread_chat ? ` (${app.counts.unread_chat})` : ""}` }, { value: "calls", label: `Calls${app.counts.missed_calls ? ` (${app.counts.missed_calls} missed)` : ""}` }]} />
        {view === "calls" ? <CallHistory /> : <>
        <Err msg={error} />
        {!data ? <Loading /> : (
          <div className="list">
            {data.map((c) => (
              <div key={c.id} className="li tap" onClick={() => app.push({ name: "conversation", params: { id: c.id, title: c.title } })}>
                {c.kind === "direct" ? <Avatar name={c.title} /> : <div className="avatar" style={{ width: 40, height: 40, background: "#e8efff", fontSize: 20 }}>{KIND_ICON[c.kind]}</div>}
                <div className="grow">
                  <div className="row between"><span className="ellipsis" style={{ fontWeight: c.unread ? 700 : 600 }}>{c.title}</span>
                    {c.last && <span className="tiny muted">{fmt.ago(c.last.created_at)}</span>}</div>
                  <div className="row between"><span className="small muted ellipsis">{c.last ? `${c.last.mine ? "You" : c.last.sender.split(" ")[0]}: ${c.last.body}` : c.kind === "direct" ? "Say hello 👋" : "No messages yet"}</span>
                    {c.unread > 0 && <span className="chip info">{c.unread}</span>}</div>
                </div>
              </div>
            ))}
          </div>
        )}
        <Card><div className="small muted">💡 To message or call someone, open <b>People</b>. Calls inside NES Team are free — on office Wi-Fi they work even without internet.</div></Card>
        </>}
      </div>
    </div>
  );
}

function CallHistory() {
  const app = useApp();
  const { data, error } = useLoad<any[]>("/mobile/calls");
  useEffect(() => { api("/mobile/calls/seen", { method: "POST" }).then(() => app.refreshCounts()).catch(() => {}); }, []); // eslint-disable-line
  if (error) return <Err msg={error} />;
  if (!data) return <Loading />;
  if (!data.length) return <Card><Empty icon="📞">No calls yet. Open People and tap 📞 to make a free call.</Empty></Card>;
  return (
    <div className="list call-hist">
      {data.map((c) => {
        const missed = c.result === "missed";
        return (
          <div key={c.id} className="li">
            <div className="ic">{c.kind === "group" ? "👥" : c.media === "video" ? "🎥" : "📞"}</div>
            <div className="grow">
              <div className={`ellipsis ${missed ? "missed" : ""}`} style={{ fontWeight: 600 }}>{c.title}</div>
              <div className="tiny muted">{c.outgoing ? "↗ Outgoing" : missed ? "↙ Missed" : "↙ Incoming"} · {c.result === "answered" && c.duration_s != null ? fmtDur(c.duration_s) : c.result} · {fmt.ago(c.started_at)}</div>
            </div>
            {c.other_user_id && (
              <button className="btn sm" aria-label="Call back" onClick={() => calls.callUser(c.other_user_id, c.title, "audio").catch((e) => window.alert(e.message))}>📞</button>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function Conversation({ id, title }: { id: string; title: string }) {
  const app = useApp();
  const [msgs, setMsgs] = useState<any[] | null>(null);
  const [info, setInfo] = useState<any>(null);
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const lastAt = useRef<string | null>(null);

  const load = async (initial = false) => {
    try {
      const q = !initial && lastAt.current ? `?after=${encodeURIComponent(lastAt.current)}` : "";
      const r = await api<any>(`/mobile/chat/${id}/messages${q}`);
      if (initial) setInfo(r.channel);
      if (r.messages.length || initial) {
        setMsgs((old) => {
          const base = initial || !old ? [] : old;
          const seen = new Set(base.map((m) => m.id));
          return [...base, ...r.messages.filter((m: any) => !seen.has(m.id))];
        });
        if (r.messages.length) {
          lastAt.current = r.messages[r.messages.length - 1].created_at;
          await api(`/mobile/chat/${id}/read`, { method: "POST" });
          app.refreshCounts();
        }
      }
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  useEffect(() => {
    load(true);
    const t = setInterval(() => load(false), 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [msgs?.length]);

  const send = async () => {
    const body = text.trim();
    if (!body) return;
    setSending(true);
    try {
      const m = await api<any>(`/mobile/chat/${id}/messages`, { body: { body } });
      setText("");
      setMsgs((old) => [...(old || []), m]);
      lastAt.current = m.created_at;
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSending(false);
    }
  };

  let lastDay = "";
  return (
    <div className="chat" style={{ height: "100vh" }}>
      <Header title={title} back={app.back} right={info && (
        <button className="icon-btn" aria-label={info.kind === "direct" ? "Free call" : "Group call"} style={{ fontSize: 22 }}
          onClick={() => (info.kind === "direct" && info.other_user_id
            ? calls.callUser(info.other_user_id, title, "audio")
            : calls.callGroup(id, title, "audio")).catch((e) => setErr(e.message))}>📞</button>
      )} />
      <div className="msgs">
        {err && <div className="err">{err}</div>}
        {!msgs ? <Loading /> : msgs.length === 0 ? <Empty icon="💬">No messages yet. Start the conversation.</Empty> : msgs.map((m) => {
          const d = new Date(m.created_at).toDateString();
          const sep = d !== lastDay;
          lastDay = d;
          return (
            <div key={m.id} style={{ display: "contents" }}>
              {sep && <div className="day-sep">{new Date(m.created_at).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })}</div>}
              <div className={`bubble ${m.mine ? "mine" : ""}`}>
                {!m.mine && <div className="who">{m.sender}</div>}
                <div style={{ fontStyle: m.deleted ? "italic" : undefined }}>{m.body}</div>
                <div className="t">{fmt.time(m.created_at)}</div>
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
      <div className="composer">
        <textarea rows={1} value={text} placeholder="Message" maxLength={4000} onChange={(e) => setText(e.target.value)} />
        <button className="send" disabled={sending || !text.trim()} onClick={send} aria-label="Send">➤</button>
      </div>
    </div>
  );
}
