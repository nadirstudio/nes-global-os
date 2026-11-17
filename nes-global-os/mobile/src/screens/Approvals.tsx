import { useApp } from "../App";
import { api, fmt } from "../api";
import { Card, Empty, Err, Header, Loading, useAction, useLoad } from "../ui";
import { openUrl } from "../native";

export function Approvals() {
  const app = useApp();
  const { data, error, reload } = useLoad<any>("/mobile/approvals");
  const act = useAction();
  const decide = (path: string, decision: string) => act.run(async () => {
    const note = decision === "rejected" ? window.prompt("Reason (optional)") ?? undefined : undefined;
    await api(path, { body: { decision, note } });
    await reload(true);
    app.refreshCounts();
  });
  const total = data ? data.leave.length + data.field_checkins.length + data.system.length : 0;
  return (
    <div className="screen">
      <Header title="Approvals" back={app.back} />
      <div className="content">
        <Err msg={error || act.err} />
        {!data ? <Loading /> : total === 0 ? <Card><Empty icon="✅">Nothing waiting for you.</Empty></Card> : (
          <>
            {data.leave.length > 0 && <div className="section-title"><span>Leave & overtime ({data.leave.length})</span></div>}
            {data.leave.map((r: any) => (
              <Card key={r.id}>
                <div className="stack" style={{ gap: 6 }}>
                  <div className="row between"><b>{r.person?.name}</b><span className="tiny muted">{fmt.ago(r.created_at)}</span></div>
                  <div>{r.label} · {r.kind === "overtime" ? `${r.hours} h` : `${r.days} day${r.days === 1 ? "" : "s"}`}</div>
                  <div className="small muted">{fmt.date(r.start_on)}{r.end_on !== r.start_on ? ` – ${fmt.date(r.end_on)}` : ""}{r.half_day ? " (half day)" : ""}</div>
                  {r.reason && <div className="small">“{r.reason}”</div>}
                  <Buttons busy={act.busy} onApprove={() => decide(`/mobile/leave/${r.id}/decide`, "approved")} onReject={() => decide(`/mobile/leave/${r.id}/decide`, "rejected")} />
                </div>
              </Card>
            ))}
            {data.field_checkins.length > 0 && <div className="section-title"><span>Field check-ins ({data.field_checkins.length})</span></div>}
            {data.field_checkins.map((a: any) => (
              <Card key={a.id}>
                <div className="stack" style={{ gap: 6 }}>
                  <div className="row between"><b>{a.person.name}</b><span className="tiny muted">{fmt.day(a.day)} · {fmt.time(a.check_in)}</span></div>
                  <div className="small">📍 {a.distance_m != null ? `${Math.round(a.distance_m)} m from ${a.nearest_site || "office"}` : "Location recorded"}</div>
                  {a.note && <div className="small">“{a.note}”</div>}
                  {a.map && <button className="btn sm" onClick={() => openUrl(a.map)}>View on map</button>}
                  <Buttons busy={act.busy} onApprove={() => decide(`/mobile/attendance/${a.id}/field-decide`, "approved")} onReject={() => decide(`/mobile/attendance/${a.id}/field-decide`, "rejected")} />
                </div>
              </Card>
            ))}
            {data.system.length > 0 && <div className="section-title"><span>Business approvals ({data.system.length})</span></div>}
            {data.system.map((a: any) => (
              <Card key={a.id}>
                <div className="stack" style={{ gap: 6 }}>
                  <b>{a.title}</b>
                  <div className="tiny muted">{fmt.label(a.kind)}{a.requested_by ? ` · requested by ${a.requested_by}` : ""} · {fmt.ago(a.created_at)}</div>
                  {a.summary && <div className="small">{a.summary}</div>}
                  <Buttons busy={act.busy} onApprove={() => decide(`/approvals/${a.id}/decide`, "approved")} onReject={() => decide(`/approvals/${a.id}/decide`, "rejected")} />
                </div>
              </Card>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function Buttons({ busy, onApprove, onReject }: { busy: boolean; onApprove: () => void; onReject: () => void }) {
  return (
    <div className="row" style={{ marginTop: 4 }}>
      <button className="btn green grow" disabled={busy} onClick={onApprove}>Approve</button>
      <button className="btn danger grow" disabled={busy} onClick={onReject}>Reject</button>
    </div>
  );
}
