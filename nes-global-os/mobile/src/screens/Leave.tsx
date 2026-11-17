import { useState } from "react";
import { useApp } from "../App";
import { api, fmt } from "../api";
import { Card, Chip, Empty, Err, Field, Header, Loading, Segmented, Sheet, useAction, useLoad } from "../ui";

const today = () => new Date().toISOString().slice(0, 10);

export function Leave() {
  const app = useApp();
  const { data, error, reload } = useLoad<any>("/mobile/leave");
  const [apply, setApply] = useState(false);
  const act = useAction();
  return (
    <div className="screen">
      <Header title="Leave & overtime" back={app.back} />
      <div className="content">
        <Err msg={error || act.err} />
        {!data ? <Loading /> : (
          <>
            <div className="balances">
              {data.balances.map((b: any) => (
                <div className="bal" key={b.kind}>
                  <div className="n">{b.remaining}</div>
                  <div className="l">{b.label}</div>
                  <div className="tiny muted">{b.used} used of {b.entitled}{b.pending ? ` · ${b.pending} pending` : ""}</div>
                </div>
              ))}
            </div>
            <button className="btn primary block" onClick={() => setApply(true)}>+ Apply for leave or overtime</button>
            <div className="section-title"><span>My requests</span></div>
            {data.requests.length ? (
              <div className="list">
                {data.requests.map((r: any) => (
                  <div className="li" key={r.id}>
                    <div className="grow">
                      <div style={{ fontWeight: 600 }}>{r.label}{r.kind === "overtime" ? ` · ${r.hours}h` : ` · ${r.days} day${r.days === 1 ? "" : "s"}`}</div>
                      <div className="tiny muted">{fmt.date(r.start_on)}{r.end_on !== r.start_on ? ` – ${fmt.date(r.end_on)}` : ""}{r.half_day ? " (half day)" : ""}</div>
                      {r.decision_note && <div className="tiny muted">Note: {r.decision_note}</div>}
                    </div>
                    <div className="stack" style={{ gap: 6, alignItems: "flex-end" }}>
                      <Chip s={r.status} />
                      {r.status === "pending" && (
                        <button className="btn sm danger" disabled={act.busy}
                          onClick={() => act.run(async () => { await api(`/mobile/leave/${r.id}/cancel`, { method: "POST" }); reload(true); })}>Cancel</button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : <Card><Empty icon="🌴">No requests yet.</Empty></Card>}
          </>
        )}
      </div>
      <ApplySheet open={apply} kinds={data?.kinds || {}} onClose={() => setApply(false)} onDone={() => { setApply(false); reload(true); }} />
    </div>
  );
}

function ApplySheet({ open, kinds, onClose, onDone }: { open: boolean; kinds: Record<string, string>; onClose: () => void; onDone: () => void }) {
  const [kind, setKind] = useState("casual");
  const [start, setStart] = useState(today());
  const [end, setEnd] = useState(today());
  const [half, setHalf] = useState(false);
  const [hours, setHours] = useState("2");
  const [reason, setReason] = useState("");
  const act = useAction();
  const ot = kind === "overtime";
  const submit = () => act.run(async () => {
    await api("/mobile/leave", {
      body: { kind, start_on: start, end_on: ot ? start : end, half_day: !ot && half && start === end, hours: ot ? Number(hours) : null, reason: reason || null },
    });
    setReason("");
    onDone();
  });
  return (
    <Sheet open={open} onClose={onClose} title="New request">
      <Segmented value={kind} onChange={setKind} options={Object.entries(kinds).map(([v, l]) => ({ value: v, label: l.replace(" leave", "") }))} />
      <div className="row">
        <div className="grow"><Field label={ot ? "Date" : "From"}><input type="date" value={start} onChange={(e) => { setStart(e.target.value); if (e.target.value > end) setEnd(e.target.value); }} /></Field></div>
        {!ot && <div className="grow"><Field label="To"><input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} /></Field></div>}
      </div>
      {ot ? (
        <Field label="Overtime hours"><input type="number" min="0.5" max="24" step="0.5" value={hours} onChange={(e) => setHours(e.target.value)} /></Field>
      ) : start === end && (
        <label className="toggle card"><span>Half day</span><input type="checkbox" checked={half} onChange={(e) => setHalf(e.target.checked)} /></label>
      )}
      <Field label="Reason (optional)"><textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} placeholder={ot ? "What did you work on?" : "e.g. Family event"} /></Field>
      <Err msg={act.err} />
      <button className="btn primary block" disabled={act.busy} onClick={submit}>{act.busy ? "Sending…" : "Send for approval"}</button>
      <div className="tiny muted">Days are counted on working days only (Mon–Sat). Your manager is notified.</div>
    </Sheet>
  );
}
