"use client";
import { useEffect, useState } from "react";

const COLORS: Record<string, string> = { ok: "#22c55e", warn: "#f59e0b", crit: "#ef4444", info: "#22d3ee", off: "#3b4a66", blue: "#3b82f6" };

export function Donut({ parts, size = 132, label, sub }: { parts: { label: string; value: number; tone: string }[]; size?: number; label: string; sub?: string }) {
  const [on, setOn] = useState(false);
  useEffect(() => { const t = setTimeout(() => setOn(true), 30); return () => clearTimeout(t); }, []);
  const total = parts.reduce((a, b) => a + b.value, 0);
  const r = 46, c = 2 * Math.PI * r;
  let off = 0;
  return (
    <div className="row" style={{ gap: 16, alignItems: "center" }}>
      <svg width={size} height={size} viewBox="0 0 120 120" role="img" aria-label={label}>
        <circle cx="60" cy="60" r={r} fill="none" stroke="#1d2a42" strokeWidth="12" />
        {total > 0 && parts.filter((p) => p.value > 0).map((p) => {
          const len = (p.value / total) * c;
          const el = (
            <circle key={p.label} cx="60" cy="60" r={r} fill="none" stroke={COLORS[p.tone] || COLORS.off} strokeWidth="12"
              strokeDasharray={`${on ? len : 0} ${c}`} strokeDashoffset={-off} transform="rotate(-90 60 60)"
              style={{ transition: "stroke-dasharray 1s cubic-bezier(.2,.8,.2,1)" }}><title>{`${p.label}: ${p.value}`}</title></circle>
          );
          off += len;
          return el;
        })}
        <text x="60" y="58" textAnchor="middle" fill="#e6edf7" fontSize="22" fontWeight="600" fontFamily="ui-monospace,monospace">{label}</text>
        {sub && <text x="60" y="76" textAnchor="middle" fill="#8a9ab5" fontSize="9" letterSpacing="1">{sub}</text>}
      </svg>
      <div className="stack" style={{ gap: 4, fontSize: 12 }}>
        {parts.map((p) => (
          <div key={p.label} className="row" style={{ gap: 8 }}>
            <span className="dot" style={{ background: COLORS[p.tone] || COLORS.off }} />
            <span className="muted" style={{ minWidth: 150 }}>{p.label}</span><b className="mono">{p.value}</b>
          </div>
        ))}
      </div>
    </div>
  );
}

export function HBars({ rows, format = (n: number) => n.toLocaleString(), empty = "No data recorded yet" }: {
  rows: { label: string; values: { v: number; tone: string; name: string }[] }[]; format?: (n: number) => string; empty?: string;
}) {
  const [on, setOn] = useState(false);
  useEffect(() => { const t = setTimeout(() => setOn(true), 30); return () => clearTimeout(t); }, []);
  const max = Math.max(1, ...rows.flatMap((r) => r.values.map((v) => v.v)));
  if (!rows.length || max <= 1 && rows.every((r) => r.values.every((v) => v.v === 0))) return <div className="empty">{empty}</div>;
  return (
    <div className="stack" style={{ gap: 9 }}>
      {rows.map((r) => (
        <div key={r.label}>
          <div className="small muted" style={{ marginBottom: 3 }}>{r.label}</div>
          {r.values.map((v) => (
            <div key={v.name} className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
              <div style={{ flex: 1, height: 7, background: "#1d2a42", borderRadius: 99, overflow: "hidden" }}>
                <div style={{ width: on ? `${(v.v / max) * 100}%` : 0, height: "100%", background: COLORS[v.tone], borderRadius: 99, transition: "width .9s cubic-bezier(.2,.8,.2,1)" }} />
              </div>
              <span className="mono small" style={{ minWidth: 110, textAlign: "right" }} title={v.name}>{format(v.v)}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

type Co = { id: string; code: string; name: string; kind: string; people: number; agents: number; open_tasks: number; overdue_tasks: number; open_leads: number; departments: number };

export function NetworkMap({ companies, onPick }: { companies: Co[]; onPick: (c: Co) => void }) {
  const parent = companies.find((c) => c.kind === "parent");
  const units = companies.filter((c) => c !== parent);
  const W = 640, H = 360, cx = W / 2, cy = H / 2;
  const R = Math.min(W, H) / 2 - 58;
  const pos = units.map((_, i) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(units.length, 1);
    return { x: cx + R * 1.45 * Math.cos(a), y: cy + R * Math.sin(a) };
  });
  const toneOf = (c: Co) => (c.overdue_tasks >= 3 ? "#ef4444" : c.overdue_tasks ? "#f59e0b" : "#22c55e");
  const short = (n: string) => n.replace("NADIR E-SKILLS (SMC-PRIVATE) LIMITED", "NADIR E-SKILLS").replace("NES ", "").replace("Nadir ", "");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Company network">
      <defs>
        <radialGradient id="glow"><stop offset="0%" stopColor="#3b82f6" stopOpacity=".45" /><stop offset="100%" stopColor="#3b82f6" stopOpacity="0" /></radialGradient>
      </defs>
      {units.map((u, i) => (
        <g key={u.id}>
          <line x1={cx} y1={cy} x2={pos[i].x} y2={pos[i].y} stroke="#27385a" strokeWidth="1.2" />
          <circle r="2.4" fill="#22d3ee">
            <animateMotion dur={`${3 + (i % 3)}s`} repeatCount="indefinite" path={`M${cx},${cy} L${pos[i].x},${pos[i].y}`} />
          </circle>
        </g>
      ))}
      {parent && (
        <g style={{ cursor: "pointer" }} onClick={() => onPick(parent)}>
          <circle cx={cx} cy={cy} r="70" fill="url(#glow)" />
          <circle cx={cx} cy={cy} r="46" fill="#0f1828" stroke="#22d3ee" strokeWidth="2" />
          <text x={cx} y={cy - 3} textAnchor="middle" fill="#e6edf7" fontSize="11" fontWeight="700" letterSpacing="1">NES GROUP</text>
          <text x={cx} y={cy + 12} textAnchor="middle" fill="#8a9ab5" fontSize="9">{parent.departments} group depts</text>
        </g>
      )}
      {units.map((u, i) => (
        <g key={u.id} style={{ cursor: "pointer" }} onClick={() => onPick(u)}>
          <title>{`${u.name}: ${u.people} people, ${u.agents} agents, ${u.open_tasks} open tasks (${u.overdue_tasks} overdue), ${u.open_leads} open leads`}</title>
          <circle cx={pos[i].x} cy={pos[i].y} r="27" fill="#0f1828" stroke={toneOf(u)} strokeWidth="2" />
          <text x={pos[i].x} y={pos[i].y + 4} textAnchor="middle" fill="#e6edf7" fontSize="10" fontWeight="600">{u.code.replace("NES-", "")}</text>
          <text x={pos[i].x} y={pos[i].y + 44} textAnchor="middle" fill="#c5d0e3" fontSize="10.5">{short(u.name)}</text>
          <text x={pos[i].x} y={pos[i].y + 57} textAnchor="middle" fill="#5b6b88" fontSize="9" fontFamily="ui-monospace,monospace">
            {u.people}p · {u.agents}ai · {u.open_tasks}t
          </text>
        </g>
      ))}
    </svg>
  );
}
