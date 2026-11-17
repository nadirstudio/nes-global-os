import { useState } from "react";
import { useApp } from "../App";
import { activeServer, api, fmt, lanServerUrl, normaliseServer, saveLanServer, serverUrl } from "../api";
import { Avatar, Card, Chip, Empty, Err, Header, Loading, useLoad } from "../ui";

export function More() {
  const app = useApp();
  const { data: h } = useLoad<any>("/mobile/home");
  const items = [
    { icon: "🌴", label: "Leave & overtime", go: "leave" },
    { icon: "🗓", label: "Shifts", go: "shifts" },
    { icon: "🕘", label: "My attendance", go: "attendance" },
    { icon: "📢", label: "Company news", go: "news", count: app.counts.unread_news },
    { icon: "📄", label: "Documents", go: "docs" },
    { icon: "🤖", label: "Ask HR assistant", go: "assistant" },
    ...(app.me.is_leader ? [{ icon: "✅", label: "Approvals", go: "approvals", count: app.counts.pending_approvals }] : []),
  ];
  return (
    <div className="screen">
      <Header title="More" />
      <div className="content">
        <Card>
          <div className="row">
            <Avatar name={app.me.name || "?"} size={56} />
            <div className="grow">
              <div style={{ fontWeight: 700, fontSize: 17 }}>{app.me.name}</div>
              <div className="small muted">{h?.person.designation || fmt.label(app.me.role)}</div>
              <div className="tiny muted">{[h?.person.department, h?.person.company].filter(Boolean).join(" · ")}{h ? ` · ID ${h.person.code}` : ""}</div>
            </div>
          </div>
        </Card>
        <div className="list">
          {items.map((i) => (
            <div key={i.go} className="li tap" onClick={() => app.push({ name: i.go })}>
              <span style={{ fontSize: 20, width: 28, textAlign: "center" }}>{i.icon}</span>
              <span className="grow" style={{ fontWeight: 550 }}>{i.label}</span>
              {!!i.count && <span className="chip bad">{i.count}</span>}
              <span className="chev">›</span>
            </div>
          ))}
        </div>
        <div className="section-title"><span>Security</span></div>
        <div className="list">
          <div className="li"><span style={{ fontSize: 20, width: 28, textAlign: "center" }}>🔒</span><span className="grow">App lock with fingerprint / face</span><Chip s="approved" label="On" /></div>
          <div className="li"><span style={{ fontSize: 20, width: 28, textAlign: "center" }}>🛡</span><span className="grow">Screenshots blocked in this app</span><Chip s="approved" label="On" /></div>
          <div className="li"><span style={{ fontSize: 20, width: 28, textAlign: "center" }}>🌐</span>
            <span className="grow small muted ellipsis">Main: {serverUrl()}<br />Office: {lanServerUrl() || "not set"}<br />Using: {activeServer() === lanServerUrl() && lanServerUrl() ? "office Wi-Fi" : "Tailscale"}</span>
            <button className="btn sm" onClick={async () => {
              const v = window.prompt("Office address (e.g. http://192.168.1.27). Leave empty to remove.", lanServerUrl());
              if (v === null) return;
              if (v.trim()) {
                try { await api("/mobile/config", { base: normaliseServer(v, "http://"), auth: false }); }
                catch { window.alert("That address doesn't answer. Connect to the office Wi-Fi and try again."); return; }
              }
              await saveLanServer(v.trim());
              window.location.reload();
            }}>Edit</button>
          </div>
        </div>
        <button className="btn danger block" onClick={() => { if (window.confirm("Sign out of NES Team on this phone?")) app.signOut(); }}>Sign out</button>
        <div className="tiny muted" style={{ textAlign: "center" }}>NES Team 1.0.0 · Nadir E-Skills (SMC-Private) Limited</div>
      </div>
    </div>
  );
}

export function Attendance() {
  const app = useApp();
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const { data, error } = useLoad<any>(`/mobile/attendance/history?month=${month}`, [month]);
  return (
    <div className="screen">
      <Header title="My attendance" back={app.back} />
      <div className="content">
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
        <Err msg={error} />
        {!data ? <Loading /> : (
          <>
            <div className="row wrap">{Object.entries(data.summary).map(([k, v]) => <Chip key={k} s={k} label={`${v} ${k}`} />)}</div>
            {data.records.length === 0 ? <Card><Empty icon="🕘">No records this month.</Empty></Card> : (
              <div className="list">
                {data.records.map((r: any) => (
                  <div key={r.id} className="li">
                    <div className="grow">
                      <div style={{ fontWeight: 600 }}>{fmt.day(r.day)}</div>
                      <div className="tiny muted">{r.check_in ? `In ${fmt.time(r.check_in)}` : ""}{r.check_out ? ` · Out ${fmt.time(r.check_out)}` : ""}{r.note ? ` · ${r.note}` : ""}</div>
                    </div>
                    <Chip s={r.status} />
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
