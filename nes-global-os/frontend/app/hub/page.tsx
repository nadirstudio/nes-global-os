"use client";
import { useState } from "react";
import Shell, { can, useMe } from "@/components/Shell";
import { Badge, Card, Empty, Err, FormModal, useAction, useLoad } from "@/components/ui";
import { api, fmt } from "@/lib/api";

function LeaveTab() {
  const [status, setStatus] = useState("pending");
  const { data, error, reload } = useLoad<any[]>(`/hub/leave?status=${status}`, [status]);
  const field = useLoad<any>("/mobile/approvals");
  const act = useAction();
  const decide = (path: string, decision: string) => act.run(async () => {
    const note = decision === "rejected" ? prompt("Reason (optional)") || undefined : undefined;
    await api(path, { body: { decision, note } });
    reload(); field.reload();
  });
  return (
    <div className="stack">
      <Err msg={error || act.err} />
      <Card title="Field check-ins waiting for review" action={<span className="small muted">Employees who checked in outside an office geofence</span>}>
        {field.data?.field_checkins?.length ? (
          <table className="tbl"><thead><tr><th>Person</th><th>Day</th><th>Distance</th><th>Note</th><th /></tr></thead><tbody>
            {field.data.field_checkins.map((a: any) => (
              <tr key={a.id}><td>{a.person.name}</td><td className="small">{a.day} {fmt.dt(a.check_in).split(", ")[1]}</td>
                <td className="small">{a.distance_m != null ? `${Math.round(a.distance_m)} m from ${a.nearest_site || "office"}` : "—"}{a.map && <> · <a href={a.map} target="_blank" rel="noreferrer">map</a></>}</td>
                <td className="small">{a.note}</td>
                <td><div className="row" style={{ flexWrap: "nowrap" }}>
                  <button className="btn sm primary" disabled={act.busy} onClick={() => decide(`/mobile/attendance/${a.id}/field-decide`, "approved")}>Approve</button>
                  <button className="btn sm danger" disabled={act.busy} onClick={() => decide(`/mobile/attendance/${a.id}/field-decide`, "rejected")}>Reject</button></div></td></tr>
            ))}</tbody></table>
        ) : <Empty>Nothing to review.</Empty>}
      </Card>
      <Card title="Leave & overtime requests" action={
        <div className="row">{["pending", "approved", "rejected", "all"].map((s) => <button key={s} className={`btn sm ${status === s ? "primary" : ""}`} onClick={() => setStatus(s)}>{fmt.label(s)}</button>)}</div>}>
        {data?.length ? (
          <table className="tbl"><thead><tr><th>Person</th><th>Type</th><th>Dates</th><th>Days / hours</th><th>Reason</th><th>Status</th><th /></tr></thead><tbody>
            {data.map((r) => (
              <tr key={r.id}><td>{r.person?.name}</td><td>{r.label}</td><td className="small">{r.start_on}{r.end_on !== r.start_on ? ` → ${r.end_on}` : ""}{r.half_day ? " (½)" : ""}</td>
                <td className="mono">{r.kind === "overtime" ? `${r.hours} h` : r.days}</td><td className="small">{r.reason || "—"}</td><td><Badge s={r.status} /></td>
                <td>{r.can_decide && <div className="row" style={{ flexWrap: "nowrap" }}>
                  <button className="btn sm primary" disabled={act.busy} onClick={() => decide(`/mobile/leave/${r.id}/decide`, "approved")}>Approve</button>
                  <button className="btn sm danger" disabled={act.busy} onClick={() => decide(`/mobile/leave/${r.id}/decide`, "rejected")}>Reject</button></div>}</td></tr>
            ))}</tbody></table>
        ) : <Empty>No {status === "all" ? "" : status} requests.</Empty>}
      </Card>
    </div>
  );
}

function SitesTab() {
  const me = useMe();
  const { data, error, reload } = useLoad<any[]>("/hub/sites");
  const companies = useLoad<any[]>("/companies");
  const [edit, setEdit] = useState<any>(null);
  const fields = [
    { name: "name", label: "Name", required: true, placeholder: "Mandi Bahauddin office" },
    { name: "company_id", label: "Company (empty = all companies)", type: "select" as const, options: (companies.data || []).map((c) => ({ value: c.id, label: c.name })) },
    { name: "kind", label: "Kind", type: "select" as const, options: [{ value: "office", label: "Office" }, { value: "branch", label: "Branch" }, { value: "client", label: "Regular client site" }] },
    { name: "radius_m", label: "Radius (metres)", type: "number" as const, help: "100–200 m works for most offices" },
    { name: "lat", label: "Latitude", type: "number" as const, required: true, help: "Google Maps → right-click the building → click the numbers to copy" },
    { name: "lng", label: "Longitude", type: "number" as const, required: true },
    { name: "active", label: "Active", type: "checkbox" as const },
  ];
  return (
    <Card title="Office locations (geofences)" action={can(me, "department.manage") && <button className="btn sm primary" onClick={() => setEdit({ kind: "office", radius_m: 150, active: true })}>+ Add location</button>}>
      <Err msg={error} />
      <div className="note small" style={{ marginBottom: 10 }}>Employees can check in when their phone's GPS is inside one of these circles. Outside, they must add a note, and the check-in goes to their manager for review. Once any location exists, check-in from the web portal is switched off for staff.</div>
      {data?.length ? (
        <table className="tbl"><thead><tr><th>Name</th><th>Company</th><th>Kind</th><th>Radius</th><th>Position</th><th>Status</th><th /></tr></thead><tbody>
          {data.map((s) => (
            <tr key={s.id}><td>{s.name}</td><td className="small">{companies.data?.find((c) => c.id === s.company_id)?.name || "All companies"}</td><td>{s.kind}</td>
              <td className="mono">{s.radius_m} m</td><td className="small"><a href={`https://maps.google.com/?q=${s.lat},${s.lng}`} target="_blank" rel="noreferrer">{Number(s.lat).toFixed(5)}, {Number(s.lng).toFixed(5)}</a></td>
              <td><Badge s={s.active ? "active" : "paused"} /></td>
              <td>{can(me, "department.manage") && <button className="btn sm" onClick={() => setEdit(s)}>Edit</button>}</td></tr>
          ))}</tbody></table>
      ) : <Empty>No locations yet — add your offices so the app can verify check-ins.</Empty>}
      {edit && <FormModal title={edit.id ? "Edit location" : "Add location"} fields={fields} initial={edit} onClose={() => setEdit(null)}
        onSubmit={async (v) => { const body = { ...v, radius_m: v.radius_m || 150, kind: v.kind || "office" };
          if (edit.id) await api(`/hub/sites/${edit.id}`, { method: "PATCH", body }); else await api("/hub/sites", { body }); reload(); }} />}
    </Card>
  );
}

function NewsTab() {
  const me = useMe();
  const { data, error, reload } = useLoad<any[]>("/mobile/news");
  const companies = useLoad<any[]>("/companies");
  const depts = useLoad<any[]>("/departments");
  const [add, setAdd] = useState(false);
  const act = useAction();
  return (
    <Card title="Announcements" action={["ceo", "director", "dept_head"].includes(me.user.role) && <button className="btn sm primary" onClick={() => setAdd(true)}>+ New announcement</button>}>
      <Err msg={error || act.err} />
      {data?.length ? data.map((n) => (
        <div key={n.id} style={{ borderBottom: "1px solid var(--line)", padding: "10px 0" }}>
          <div className="row between"><b style={{ fontWeight: 600 }}>{n.pinned ? "📌 " : ""}{n.title}</b>
            <div className="row">{n.priority === "urgent" && <Badge s="critical" label="urgent" />}<span className="small faint">{n.audience} · {fmt.dt(n.created_at)}</span>
              <button className="btn sm danger" onClick={() => confirm("Delete this announcement?") && act.run(async () => { await api(`/mobile/news/${n.id}`, { method: "DELETE" }); reload(); })}>Delete</button></div></div>
          <div className="small muted" style={{ whiteSpace: "pre-wrap" }}>{n.body}</div>
        </div>
      )) : <Empty>No announcements yet.</Empty>}
      {add && <FormModal title="New announcement" submitLabel="Publish" onClose={() => setAdd(false)} initial={{ priority: "normal" }}
        fields={[{ name: "title", label: "Title", required: true, full: true },
          { name: "company_id", label: "Company (empty = whole group, CEO only)", type: "select", options: (companies.data || []).map((c) => ({ value: c.id, label: c.name })) },
          { name: "department_id", label: "…or only one department", type: "select", options: (depts.data || []).map((d) => ({ value: d.id, label: `${d.name} — ${companies.data?.find((c) => c.id === d.company_id)?.code || ""}` })) },
          { name: "priority", label: "Priority", type: "select", options: [{ value: "normal", label: "Normal" }, { value: "urgent", label: "Urgent (alerts phones)" }] },
          { name: "pinned", label: "Pin to top", type: "checkbox" },
          { name: "body", label: "Message", type: "textarea", required: true }]}
        onSubmit={async (v) => { await api("/mobile/news", { body: { ...v, priority: v.priority || "normal", pinned: !!v.pinned } }); reload(); }} />}
    </Card>
  );
}

function DocsTab() {
  const me = useMe();
  const { data, error, reload } = useLoad<any[]>("/hub/documents");
  const companies = useLoad<any[]>("/companies");
  const depts = useLoad<any[]>("/departments");
  const people = useLoad<any[]>("/people");
  const [form, setForm] = useState(false);
  const [f, setF] = useState<any>({ category: "policy" });
  const [file, setFile] = useState<File | null>(null);
  const act = useAction();
  const upload = () => act.run(async () => {
    const fd = new FormData();
    for (const [k, v] of Object.entries(f)) if (v !== "" && v != null) fd.append(k, String(v));
    if (file) fd.append("file", file);
    const r = await fetch("/api/hub/documents", { method: "POST", body: fd, credentials: "same-origin" });
    if (!r.ok) {
      const d = (await r.json().catch(() => ({}))).detail;
      throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x: any) => x.msg).join("; ") : `Upload failed (${r.status})`);
    }
    setForm(false); setF({ category: "policy" }); setFile(null); reload();
  });
  return (
    <Card title="Document hub" action={["ceo", "director", "dept_head"].includes(me.user.role) && <button className="btn sm primary" onClick={() => setForm(true)}>+ Publish document</button>}>
      <Err msg={error || act.err} />
      <div className="note small" style={{ marginBottom: 10 }}>Policies, SOPs and handbooks published here appear in the app and are used by the AI help desk to answer staff questions. Text is extracted automatically from PDF, Word and text files.</div>
      {data?.length ? (
        <table className="tbl"><thead><tr><th>Title</th><th>Category</th><th>Audience</th><th>File</th><th>Updated</th><th /></tr></thead><tbody>
          {data.map((d) => (
            <tr key={d.id}><td>{d.title}</td><td>{fmt.label(d.category)}</td>
              <td className="small">{d.person_id ? `Personal: ${people.data?.find((p) => p.id === d.person_id)?.full_name || ""}` : d.department_id ? depts.data?.find((x) => x.id === d.department_id)?.name : d.company_id ? companies.data?.find((c) => c.id === d.company_id)?.name : "Whole group"}{d.leaders_only ? " · leaders only" : ""}</td>
              <td className="small">{d.file_name ? `${d.file_name} (${Math.round((d.size_bytes || 0) / 1024)} KB)` : "text only"}</td><td className="small">{fmt.date(d.updated_at)}</td>
              <td><button className="btn sm danger" onClick={() => confirm("Delete this document?") && act.run(async () => { await api(`/hub/documents/${d.id}`, { method: "DELETE" }); reload(); })}>Delete</button></td></tr>
          ))}</tbody></table>
      ) : <Empty>No documents yet.</Empty>}
      {form && (
        <div className="overlay modal-wrap" onMouseDown={(e) => e.target === e.currentTarget && setForm(false)}>
          <div className="modal stack">
            <div className="row between"><h1>Publish document</h1><button className="btn sm ghost" onClick={() => setForm(false)}>✕</button></div>
            <div className="grid g2">
              <label className="f span2">Title *<input value={f.title || ""} onChange={(e) => setF({ ...f, title: e.target.value })} /></label>
              <label className="f">Category<select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
                {["policy", "sop", "handbook", "training", "contract", "form"].map((c) => <option key={c} value={c}>{fmt.label(c)}</option>)}</select></label>
              <label className="f">Company (empty = whole group)<select value={f.company_id || ""} onChange={(e) => setF({ ...f, company_id: e.target.value })}>
                <option value="">—</option>{companies.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
              <label className="f">…or one department<select value={f.department_id || ""} onChange={(e) => setF({ ...f, department_id: e.target.value })}>
                <option value="">—</option>{depts.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
              <label className="f">…or one person (e.g. their contract)<select value={f.person_id || ""} onChange={(e) => setF({ ...f, person_id: e.target.value })}>
                <option value="">—</option>{people.data?.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}</select></label>
              <label className="f">Leaders only<input type="checkbox" style={{ width: 18 }} checked={!!f.leaders_only} onChange={(e) => setF({ ...f, leaders_only: e.target.checked })} /></label>
              <label className="f span2">File (PDF, Word, Excel, image, text — max 20 MB)<input type="file" accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.txt,.md" onChange={(e) => setFile(e.target.files?.[0] || null)} /></label>
              <label className="f span2">Text (optional — or instead of a file)<textarea rows={5} value={f.body_text || ""} onChange={(e) => setF({ ...f, body_text: e.target.value })} /></label>
            </div>
            <Err msg={act.err} />
            <div className="row" style={{ justifyContent: "flex-end" }}><button className="btn" onClick={() => setForm(false)}>Cancel</button>
              <button className="btn primary" disabled={act.busy || !f.title} onClick={upload}>{act.busy ? "Uploading…" : "Publish"}</button></div>
          </div>
        </div>
      )}
    </Card>
  );
}

function ShiftsTab() {
  const people = useLoad<any[]>("/people");
  const sites = useLoad<any[]>("/hub/sites");
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10));
  const team = useLoad<any>(`/mobile/shifts/team?day=${day}`, [day]);
  const [edit, setEdit] = useState<any>(null);
  return (
    <Card title="Shift roster" action={<input type="date" value={day} onChange={(e) => setDay(e.target.value)} style={{ width: 170 }} />}>
      <Err msg={team.error} />
      <div className="faint small" style={{ marginBottom: 8 }}>Everyone follows standard office hours unless you set a special shift for a day.</div>
      {team.data?.team?.length ? (
        <table className="tbl"><thead><tr><th>Person</th><th>Shift</th><th>Attendance</th><th /></tr></thead><tbody>
          {team.data.team.map((t: any) => (
            <tr key={t.person.id}><td>{t.person.name}<div className="faint small">{t.person.designation}</div></td>
              <td>{t.shift.off ? "Day off" : `${t.shift.start} – ${t.shift.end}`}{t.shift.custom && <Badge s="info" label="special" />}{t.shift.site ? <span className="small faint"> · {t.shift.site}</span> : null}</td>
              <td><Badge s={t.attendance?.status || "unmarked"} />{t.attendance?.check_in && <span className="small faint"> in {fmt.dt(t.attendance.check_in).split(", ")[1]}</span>}</td>
              <td><div className="row" style={{ flexWrap: "nowrap" }}><button className="btn sm" onClick={() => setEdit({ person_id: t.person.id, day, start_time: t.shift.start || "09:00", end_time: t.shift.end || "17:00" })}>Set</button>
                {t.shift.custom && <button className="btn sm danger" onClick={async () => { await api(`/mobile/shifts/${t.person.id}/${day}`, { method: "DELETE" }); team.reload(); }}>Clear</button>}</div></td></tr>
          ))}</tbody></table>
      ) : <Empty>No team members in your scope.</Empty>}
      {edit && <FormModal title={`Shift on ${edit.day}`} initial={edit} onClose={() => setEdit(null)}
        fields={[{ name: "person_id", label: "Person", type: "select", required: true, options: (people.data || []).map((p) => ({ value: p.id, label: p.full_name })) },
          { name: "day", label: "Day", type: "date", required: true },
          { name: "start_time", label: "Start (HH:MM)", required: true }, { name: "end_time", label: "End (HH:MM)", required: true },
          { name: "site_id", label: "Location", type: "select", options: (sites.data || []).map((s) => ({ value: s.id, label: s.name })) },
          { name: "note", label: "Note" }]}
        onSubmit={async (v) => { await api("/mobile/shifts", { method: "PUT", body: v }); team.reload(); }} />}
    </Card>
  );
}

function DevicesTab() {
  const { data, error, reload } = useLoad<any[]>("/hub/devices");
  const act = useAction();
  return (
    <Card title="Phones signed in to NES Team">
      <Err msg={error || act.err} />
      <div className="note small" style={{ marginBottom: 10 }}>If a phone is lost or an employee leaves, click <b>Sign out &amp; wipe</b>. The next time that phone connects, the app signs out and deletes all company data it stored. Disabling the person's login (Workforce) also blocks every device.</div>
      {data?.length ? (
        <table className="tbl"><thead><tr><th>Person</th><th>Device</th><th>Signed in</th><th>Last seen</th><th>Status</th><th /></tr></thead><tbody>
          {data.map((d) => (
            <tr key={d.id}><td>{d.user}<div className="faint small">{d.email}</div></td><td className="small">{d.name || "—"} · {d.platform} {d.app_version}</td>
              <td className="small">{fmt.dt(d.created_at)}</td><td className="small">{fmt.dt(d.last_seen_at)}<div className="faint small mono">{d.last_ip}</div></td>
              <td>{d.revoked_at ? <Badge s="failed" label={d.wipe ? "wiped" : "signed out"} /> : <Badge s="active" />}</td>
              <td>{!d.revoked_at && <button className="btn sm danger" disabled={act.busy} onClick={() => confirm(`Sign out ${d.user}'s phone and wipe company data from it?`) && act.run(async () => { await api(`/hub/devices/${d.id}/revoke`, { body: { wipe: true } }); reload(); })}>Sign out &amp; wipe</button>}</td></tr>
          ))}</tbody></table>
      ) : <Empty>No phones have signed in yet.</Empty>}
    </Card>
  );
}

function PoliciesTab() {
  const me = useMe();
  const { data, reload } = useLoad<any>("/hub/policies");
  const [leave, setLeave] = useState(false);
  const [att, setAtt] = useState(false);
  if (!data) return <Empty>Loading…</Empty>;
  return (
    <div className="grid g2">
      <Card title="Leave entitlements (days per year)" action={can(me, "company.manage") && <button className="btn sm" onClick={() => setLeave(true)}>Edit</button>}>
        <dl className="kv"><dt>Annual</dt><dd>{data.leave.annual}</dd><dt>Casual</dt><dd>{data.leave.casual}</dd><dt>Sick</dt><dd>{data.leave.sick}</dd>
          <dt>Unpaid / overtime</dt><dd>No limit (needs approval)</dd></dl>
      </Card>
      <Card title="Attendance rules" action={can(me, "company.manage") && <button className="btn sm" onClick={() => setAtt(true)}>Edit</button>}>
        <dl className="kv"><dt>Fingerprint/face</dt><dd>{data.attendance.require_biometric ? "Required" : "Optional"}</dd>
          <dt>Late after</dt><dd>{data.attendance.late_grace_minutes} min past shift start</dd>
          <dt>Max GPS error</dt><dd>±{data.attendance.max_gps_accuracy_m} m</dd>
          <dt>Web check-in</dt><dd>{data.attendance.allow_web_checkin_with_sites ? "Allowed" : "Off when locations exist"}</dd></dl>
      </Card>
      {leave && <FormModal title="Leave entitlements" initial={data.leave} onClose={() => setLeave(false)}
        fields={[{ name: "annual", label: "Annual", type: "number", required: true }, { name: "casual", label: "Casual", type: "number", required: true }, { name: "sick", label: "Sick", type: "number", required: true }]}
        onSubmit={async (v) => { await api("/hub/policies/leave", { method: "PUT", body: v }); reload(); }} />}
      {att && <FormModal title="Attendance rules" initial={data.attendance} onClose={() => setAtt(false)}
        fields={[{ name: "require_biometric", label: "Require fingerprint / face", type: "checkbox" },
          { name: "late_grace_minutes", label: "Grace minutes before 'late'", type: "number", required: true },
          { name: "max_gps_accuracy_m", label: "Reject GPS worse than (m)", type: "number", required: true },
          { name: "allow_web_checkin_with_sites", label: "Also allow check-in from the web portal", type: "checkbox" }]}
        onSubmit={async (v) => { await api("/hub/policies/attendance", { method: "PUT", body: v }); reload(); }} />}
    </div>
  );
}

function Hub() {
  const me = useMe();
  const tabs = [["leave", "Leave & field check-ins"], ["sites", "Office locations"], ["news", "Announcements"], ["docs", "Documents"],
    ["shifts", "Shifts"], ...(can(me, "users.manage") ? [["devices", "Phones"]] : []), ["policies", "HR rules"]];
  const [tab, setTab] = useState("leave");
  return (
    <>
      <div className="tabs">{tabs.map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
      {tab === "leave" && <LeaveTab />}{tab === "sites" && <SitesTab />}{tab === "news" && <NewsTab />}{tab === "docs" && <DocsTab />}
      {tab === "shifts" && <ShiftsTab />}{tab === "devices" && <DevicesTab />}{tab === "policies" && <PoliciesTab />}
    </>
  );
}

export default function Page() {
  return <Shell title="Employee Hub" sub="Everything behind the NES Team app: approvals, office geofences, news, documents, shifts, phones and HR rules"><Hub /></Shell>;
}
