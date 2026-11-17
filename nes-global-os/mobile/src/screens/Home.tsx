import { useEffect, useState } from "react";
import { useApp } from "../App";
import { api, ApiError, fmt } from "../api";
import { confirmIdentity, getLocation } from "../native";
import { Card, Chip, Err, Loading, Sheet, useLoad } from "../ui";

type Step = "idle" | "locating" | "confirming" | "sending" | "outside" | "done";

export function Home() {
  const app = useApp();
  const { data: h, error, reload } = useLoad<any>("/mobile/home");
  const [sheet, setSheet] = useState(false);
  useEffect(() => {
    if (h) app.setMe({ name: h.person.name, role: h.role, is_leader: h.is_leader, person_id: h.person.id });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [h]);
  useEffect(() => { const t = setInterval(() => reload(true), 60000); return () => clearInterval(t); }, [reload]);

  if (error && !h) return <div className="screen"><div className="content"><Err msg={error} /><button className="btn block" onClick={() => reload()}>Try again</button></div></div>;
  if (!h) return <div className="screen"><Loading /></div>;

  const att = h.attendance;
  const checkedIn = !!att?.check_in;
  const checkedOut = !!att?.check_out;
  const onLeave = att?.status === "leave";
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="screen">
      <div className="hero">
        <div className="row between">
          <div>
            <div className="sub">{greet}</div>
            <div className="hi">{h.person.name.split(" ")[0]} 👋</div>
            <div className="sub">{h.person.designation || h.person.department || ""}{h.person.company ? ` · ${h.person.company}` : ""}</div>
          </div>
        </div>
        <div className="checkin">
          <button
            className={`big-btn ${onLeave || checkedOut ? "done" : checkedIn ? "out" : "in"}`}
            disabled={onLeave || checkedOut}
            onClick={() => setSheet(true)}
          >
            <span className="ic">{onLeave ? "🌴" : checkedOut ? "✓" : checkedIn ? "⏏" : "☝"}</span>
            {onLeave ? "On leave" : checkedOut ? "Done" : checkedIn ? "Check out" : "Check in"}
          </button>
          <div className="grow">
            <div style={{ fontWeight: 650 }}>
              {onLeave ? "Enjoy your leave" : checkedOut ? "Day complete" : checkedIn ? `Checked in ${fmt.time(att.check_in)}` : h.working_day ? "Not checked in yet" : "Day off today"}
            </div>
            <div className="sub">
              {h.shift.off ? "No shift today" : `Shift ${h.shift.start}–${h.shift.end}${h.shift.site ? ` · ${h.shift.site}` : ""}`}
            </div>
            {att && <div style={{ marginTop: 6 }}><Chip s={att.status} />{att.outside_geofence && <> <Chip s={att.field_approved ? "approved" : att.field_approved === false ? "rejected" : "pending"} label={att.field_approved ? "field ok" : att.field_approved === false ? "field rejected" : "field review"} /></>}</div>}
            {checkedOut && <div className="sub">Out at {fmt.time(att.check_out)}</div>}
          </div>
        </div>
      </div>

      <div className="content">
        <div className="tiles">
          <Tile icon="🌴" label="Leave" onClick={() => app.push({ name: "leave" })} />
          <Tile icon="🗓" label="Shifts" onClick={() => app.push({ name: "shifts" })} />
          <Tile icon="📢" label="News" count={h.unread_news} onClick={() => app.push({ name: "news" })} />
          <Tile icon="📄" label="Documents" onClick={() => app.push({ name: "docs" })} />
          <Tile icon="🤖" label="Ask HR" onClick={() => app.push({ name: "assistant" })} />
          <Tile icon="🕘" label="Attendance" onClick={() => app.push({ name: "attendance" })} />
          {h.is_leader && <Tile icon="✅" label="Approvals" count={h.pending_approvals} onClick={() => app.push({ name: "approvals" })} />}
          <Tile icon="💬" label="Chat & calls" count={h.unread_chat + (h.missed_calls || 0)} onClick={() => app.setTab("chat")} />
        </div>

        <div className="section-title"><span>Leave balance {new Date().getFullYear()}</span><a onClick={() => app.push({ name: "leave" })}>Apply</a></div>
        <div className="balances">
          {h.leave_balances.map((b: any) => (
            <div className="bal" key={b.kind}><div className="n">{b.remaining}</div><div className="l">{b.label.replace(" leave", "")} left</div></div>
          ))}
        </div>

        <div className="section-title"><span>My tasks ({h.tasks.open})</span><a onClick={() => app.setTab("tasks")}>All</a></div>
        {h.tasks.next.length ? (
          <div className="list">
            {h.tasks.next.map((t: any) => (
              <div key={t.id} className="li tap" onClick={() => app.push({ name: "task", params: { id: t.id } })}>
                <div className="grow"><div className="ellipsis" style={{ fontWeight: 550 }}>{t.title}</div>
                  <div className="tiny muted">{t.due_at ? `Due ${fmt.date(t.due_at)}` : "No due date"}</div></div>
                <Chip s={t.overdue ? "overdue" : t.status} label={t.overdue ? "overdue" : undefined} />
              </div>
            ))}
          </div>
        ) : <Card><div className="muted small">No open tasks. 🎉</div></Card>}

        {h.news.length > 0 && (
          <>
            <div className="section-title"><span>Latest news</span><a onClick={() => app.push({ name: "news" })}>All</a></div>
            <div className="list">
              {h.news.map((n: any) => (
                <div key={n.id} className="li tap" onClick={() => app.push({ name: "news" })}>
                  <div className="grow"><div className="ellipsis" style={{ fontWeight: n.read ? 500 : 700 }}>{n.priority === "urgent" ? "🔴 " : ""}{n.title}</div>
                    <div className="tiny muted">{n.audience} · {fmt.ago(n.created_at)}</div></div>
                  {!n.read && <span className="chip info">new</span>}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <CheckSheet open={sheet} checkedIn={checkedIn} onClose={() => setSheet(false)} onDone={() => { reload(true); }} />
    </div>
  );
}

function Tile({ icon, label, onClick, count }: { icon: string; label: string; onClick: () => void; count?: number }) {
  return (
    <div className="tile" onClick={onClick} role="button">
      <div className="ti">{icon}</div>{label}
      {!!count && count > 0 && <span className="dotcount">{count}</span>}
    </div>
  );
}

function CheckSheet({ open, checkedIn: checkedInNow, onClose, onDone }: { open: boolean; checkedIn: boolean; onClose: () => void; onDone: () => void }) {
  // Freeze the mode when the sheet opens, so the home screen refreshing behind it can't flip it.
  const [checkedIn, setCheckedIn] = useState(checkedInNow);
  const [step, setStep] = useState<Step>("idle");
  const [err, setErr] = useState<string | null>(null);
  const [fix, setFix] = useState<any>(null);
  const [outside, setOutside] = useState<any>(null);
  const [note, setNote] = useState("");
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    if (open) { setCheckedIn(checkedInNow); setStep("idle"); setErr(null); setOutside(null); setNote(""); setResult(null); start(checkedInNow); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const start = async (out: boolean = checkedIn) => {
    try {
      setStep("locating");
      const f = await getLocation();
      setFix(f);
      if (out) {
        setStep("sending");
        const r = await api<any>("/mobile/attendance/check-out", { body: { lat: f.lat, lng: f.lng } });
        setResult(r.attendance);
        setStep("done");
        onDone();
        return;
      }
      await submit(f, null);
    } catch (e) {
      setErr((e as Error).message);
      setStep("idle");
    }
  };

  const submit = async (f: any, fieldNote: string | null) => {
    setStep("confirming");
    const ok = await confirmIdentity("Confirm it's you to check in");
    if (!ok) { setErr("Check-in cancelled."); setStep("idle"); return; }
    setStep("sending");
    try {
      const r = await api<any>("/mobile/attendance/check-in", {
        body: { lat: f.lat, lng: f.lng, accuracy_m: f.accuracy, biometric_confirmed: true, field_note: fieldNote },
      });
      setResult({ ...r.attendance, site: r.site, geofence_configured: r.geofence_configured });
      setStep("done");
      onDone();
    } catch (e) {
      const d = (e as ApiError).detail;
      if (d?.outside_geofence) { setOutside(d); setStep("outside"); }
      else { setErr((e as Error).message); setStep("idle"); }
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title={checkedIn ? "Check out" : "Check in"}>
      {step === "locating" && <Busy text="Finding your location…" />}
      {step === "confirming" && <Busy text="Confirm with your fingerprint or face…" />}
      {step === "sending" && <Busy text="Saving…" />}
      {step === "outside" && outside && (
        <div className="stack">
          <div className="warnmsg">📍 You are about <b>{outside.distance_m >= 1000 ? `${(outside.distance_m / 1000).toFixed(1)} km` : `${outside.distance_m} m`}</b> from {outside.nearest_site}.</div>
          <div className="small muted">At a client site or on field work? Add a short note. Your manager will review this check-in.</div>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Visiting client at City Mall for website meeting" maxLength={500} />
          <button className="btn primary block" disabled={note.trim().length < 5} onClick={() => submit(fix, note.trim())}>Check in as field work</button>
          <button className="btn block" onClick={onClose}>Cancel</button>
        </div>
      )}
      {step === "done" && result && (
        <div className="stack" style={{ alignItems: "center", textAlign: "center" }}>
          <div style={{ fontSize: 52 }}>{checkedIn ? "👋" : result.outside_geofence ? "📝" : "✅"}</div>
          <h2>{checkedIn ? "Checked out" : result.outside_geofence ? "Field check-in sent for review" : result.status === "late" ? "Checked in (late)" : "Checked in"}</h2>
          <div className="muted">{fmt.time(checkedIn ? result.check_out : result.check_in)}{result.site && !result.outside_geofence ? ` · ${result.site}` : ""}</div>
          {result.geofence_configured === false && <div className="note small">Office locations aren't set up yet, so your GPS position was recorded without a geofence check.</div>}
          <button className="btn primary block" onClick={onClose}>Done</button>
        </div>
      )}
      {step === "idle" && (
        <div className="stack">
          <Err msg={err} />
          <button className="btn primary block" onClick={() => start()}>Try again</button>
          <button className="btn block" onClick={onClose}>Close</button>
        </div>
      )}
    </Sheet>
  );
}

function Busy({ text }: { text: string }) {
  return <div className="empty" style={{ padding: 30 }}><div className="spinner" />{text}</div>;
}
