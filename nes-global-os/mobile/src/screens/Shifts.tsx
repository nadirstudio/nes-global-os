import { useState } from "react";
import { useApp } from "../App";
import { fmt } from "../api";
import { Chip, Err, Header, Loading, Segmented, useLoad } from "../ui";

export function Shifts() {
  const app = useApp();
  const [view, setView] = useState<"mine" | "team">("mine");
  const mine = useLoad<any[]>("/mobile/shifts?days=14");
  const team = useLoad<any>(app.me.is_leader && view === "team" ? "/mobile/shifts/team" : null, [view]);
  return (
    <div className="screen">
      <Header title="Shifts" back={app.back} />
      <div className="content">
        {app.me.is_leader && <Segmented value={view} onChange={setView} options={[{ value: "mine", label: "My shifts" }, { value: "team", label: "Team today" }]} />}
        {view === "mine" ? (
          <>
            <Err msg={mine.error} />
            {!mine.data ? <Loading /> : (
              <div className="list">
                {mine.data.map((s) => (
                  <div className="li" key={s.day}>
                    <div className="grow">
                      <div style={{ fontWeight: 600 }}>{fmt.day(s.day)}</div>
                      <div className="tiny muted">{s.off ? "Day off" : `${s.start} – ${s.end}`}{s.site ? ` · ${s.site}` : ""}{s.note && !s.off ? ` · ${s.note}` : ""}</div>
                    </div>
                    {s.off ? <Chip s="cancelled" label="off" /> : s.custom ? <Chip s="in_progress" label="special" /> : null}
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            <Err msg={team.error} />
            {!team.data ? <Loading /> : (
              <div className="list">
                {team.data.team.map((t: any) => (
                  <div className="li" key={t.person.id}>
                    <div className="grow">
                      <div style={{ fontWeight: 600 }}>{t.person.name}</div>
                      <div className="tiny muted">{t.shift.off ? "Day off" : `${t.shift.start} – ${t.shift.end}`}{t.attendance?.check_in ? ` · in ${fmt.time(t.attendance.check_in)}` : ""}</div>
                    </div>
                    <Chip s={t.attendance?.status || "todo"} label={t.attendance?.status || "not in"} />
                  </div>
                ))}
              </div>
            )}
            <div className="tiny muted">To change a shift, use the NES portal → Employee Hub.</div>
          </>
        )}
      </div>
    </div>
  );
}
