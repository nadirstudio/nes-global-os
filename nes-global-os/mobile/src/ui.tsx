import { ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

export function useLoad<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);
  const reload = useCallback(async (quiet = false) => {
    if (!path) return;
    if (!quiet) setLoading(true);
    try {
      const d = await api<T>(path);
      if (alive.current) { setData(d); setError(null); }
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    } finally {
      if (alive.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => { reload(); }, [reload]);
  return { data, error, loading, reload, setData };
}

export function useAction() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const run = async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
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
  return { busy, err, setErr, run };
}

export function Header({ title, back, right }: { title: string; back?: () => void; right?: ReactNode }) {
  return (
    <header className="hdr">
      {back ? <button className="icon-btn" onClick={back} aria-label="Back">‹</button> : <span className="hdr-pad" />}
      <h1>{title}</h1>
      <div className="hdr-right">{right}</div>
    </header>
  );
}

export function Card({ children, onClick, className = "" }: { children: ReactNode; onClick?: () => void; className?: string }) {
  return <div className={`card ${onClick ? "tap" : ""} ${className}`} onClick={onClick}>{children}</div>;
}

const TONE: Record<string, string> = {
  present: "ok", approved: "ok", done: "ok", remote: "info", in_progress: "info", review: "info", pending: "warn",
  late: "warn", todo: "muted", blocked: "warn", rejected: "bad", absent: "bad", cancelled: "muted", leave: "info",
  urgent: "bad", overdue: "bad",
};

export function Chip({ s, label }: { s: string; label?: string }) {
  return <span className={`chip ${TONE[s] || "muted"}`}>{label ?? s.replace(/_/g, " ")}</span>;
}

export function Err({ msg }: { msg?: string | null }) {
  return msg ? <div className="err" role="alert">{msg}</div> : null;
}

export function Empty({ icon = "○", children }: { icon?: string; children: ReactNode }) {
  return <div className="empty"><div className="empty-ic">{icon}</div>{children}</div>;
}

export function Loading() {
  return <div className="empty"><div className="spinner" />Loading…</div>;
}

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="sheet-bg" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet" role="dialog" aria-modal="true">
        <div className="sheet-grip" />
        <div className="row between"><h2>{title}</h2><button className="icon-btn sm" onClick={onClose} aria-label="Close">✕</button></div>
        {children}
      </div>
    </div>
  );
}

export function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) % 360;
  return (
    <div className="avatar" style={{ width: size, height: size, fontSize: size * 0.38, background: `hsl(${h} 55% 45%)` }}>
      {name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase()}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function Segmented<T extends string>({ value, options, onChange }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button key={o.value} type="button" className={value === o.value ? "on" : ""} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}
