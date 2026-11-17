"use client";
import { ReactNode, useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";

// ---------------------------------------------------------------- data hook
export function useLoad<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => { reload(); }, [reload]);
  return { data, error, loading, reload, setData };
}

// ---------------------------------------------------------------- status → tone
const TONE: Record<string, string> = {
  CONNECTED: "ok", OPERATIONAL: "ok", ACTIVE: "ok", active: "ok", good: "ok", done: "ok", approved: "ok", won: "ok",
  paid: "ok", present: "ok", succeeded: "ok", remote: "ok",
  "CONFIGURED (UNTESTED)": "info", configured: "info", testing: "info", info: "info", review: "info", in_progress: "info",
  planning: "info", open: "info", issued: "info", todo: "off",
  "DEGRADED (FALLBACK)": "warn", PAUSED: "warn", paused: "warn", attention: "warn", warning: "warn", pending: "warn",
  late: "warn", partial: "warn", blocked: "warn", on_hold: "warn", "BUDGET LIMIT": "warn", leave: "warn",
  ERROR: "crit", "AUTHENTICATION REQUIRED": "crit", "QUOTA EXHAUSTED": "crit", critical: "crit", rejected: "crit",
  failed: "crit", absent: "crit", lost: "crit", overdue: "crit",
  "NOT CONNECTED": "off", "NOT OPERATIONAL": "off", "NOT ACTIVE": "off", draft: "off", archived: "off", no_data: "off",
  unmarked: "off", cancelled: "off",
};
export const tone = (s?: string | null) => (s ? TONE[s] || (s.startsWith("ERROR") ? "crit" : "off") : "off");

export function Badge({ s, label, pulse }: { s?: string | null; label?: string; pulse?: boolean }) {
  const text = label ?? (s ? s.replace(/_/g, " ") : "—");
  return <span className={`badge ${tone(s)} ${pulse ? "pulse" : ""}`}>{text}</span>;
}

export function Card({ title, action, children, className = "" }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (<header><h2>{title}</h2>{action}</header>)}
      {children}
    </section>
  );
}

export function Stat({ label, value, detail, state }: { label: string; value: ReactNode; detail?: ReactNode; state?: "ok" | "warn" | "crit" }) {
  return (
    <div className={`card stat ${state || ""}`}>
      <div className="l">{label}</div>
      <div className="v">{value}</div>
      {detail && <div className="d">{detail}</div>}
    </div>
  );
}

export function Bar({ pct, state }: { pct: number; state?: string }) {
  return <div className={`bar ${state || ""}`}><i style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} /></div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Err({ msg }: { msg?: string | null }) {
  return msg ? <div className="err" role="alert">{msg}</div> : null;
}

export function Drawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  if (!open) return null;
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className="drawer" role="dialog" aria-modal="true">
        <div className="row between" style={{ marginBottom: 10 }}>
          <span />
          <button className="btn sm ghost" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {children}
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------- generic form modal
export type Field = {
  name: string;
  label: string;
  type?: "text" | "number" | "date" | "datetime-local" | "textarea" | "select" | "email" | "password" | "tags" | "checkbox";
  options?: { value: string; label: string }[];
  required?: boolean;
  placeholder?: string;
  full?: boolean;
  help?: string;
};

export function FormModal({ title, fields, initial = {}, submitLabel = "Save", onSubmit, onClose }: {
  title: string; fields: Field[]; initial?: Record<string, any>; submitLabel?: string;
  onSubmit: (v: Record<string, any>) => Promise<unknown>; onClose: () => void;
}) {
  const [v, setV] = useState<Record<string, any>>(() => {
    const o: Record<string, any> = {};
    fields.forEach((f) => {
      const x = initial[f.name];
      o[f.name] = f.type === "tags" ? (Array.isArray(x) ? x.join(", ") : x ?? "") : f.type === "checkbox" ? !!x : x ?? "";
    });
    return o;
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    const out: Record<string, any> = {};
    for (const f of fields) {
      let x = v[f.name];
      if (f.type === "tags") x = String(x || "").split(",").map((s) => s.trim()).filter(Boolean);
      else if (f.type === "number") x = x === "" ? null : Number(x);
      else if (f.type === "datetime-local") x = x ? new Date(x).toISOString() : null;
      else if (f.type !== "checkbox" && x === "") x = null;
      out[f.name] = x;
    }
    try {
      await onSubmit(out);
      onClose();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="overlay modal-wrap" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal stack" onSubmit={submit} role="dialog" aria-modal="true">
        <div className="row between"><h1>{title}</h1><button type="button" className="btn sm ghost" onClick={onClose}>✕</button></div>
        <div className="grid g2">
          {fields.map((f) => (
            <label key={f.name} className={`f ${f.full || f.type === "textarea" ? "span2" : ""}`}>
              <span>{f.label}{f.required && " *"}</span>
              {f.type === "textarea" ? (
                <textarea rows={4} value={v[f.name]} required={f.required} placeholder={f.placeholder}
                  onChange={(e) => setV({ ...v, [f.name]: e.target.value })} />
              ) : f.type === "select" ? (
                <select value={v[f.name]} required={f.required} onChange={(e) => setV({ ...v, [f.name]: e.target.value })}>
                  <option value="">—</option>
                  {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ) : f.type === "checkbox" ? (
                <input type="checkbox" style={{ width: 18 }} checked={!!v[f.name]} onChange={(e) => setV({ ...v, [f.name]: e.target.checked })} />
              ) : (
                <input type={f.type === "tags" ? "text" : f.type || "text"} value={v[f.name]} required={f.required}
                  placeholder={f.placeholder ?? (f.type === "tags" ? "comma, separated" : undefined)}
                  step={f.type === "number" ? "any" : undefined}
                  onChange={(e) => setV({ ...v, [f.name]: e.target.value })} />
              )}
              {f.help && <span className="faint small">{f.help}</span>}
            </label>
          ))}
        </div>
        <Err msg={err} />
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? "Saving…" : submitLabel}</button>
        </div>
      </form>
    </div>
  );
}

export function useAction() {
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setErr(null);
    try {
      return await fn();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return { err, busy, run, setErr };
}
