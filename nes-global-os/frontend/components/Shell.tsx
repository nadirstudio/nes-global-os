"use client";
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";

export type Me = {
  user: { id: string; email: string; role: string; mfa_enabled: boolean };
  role_label: string;
  person: { id: string; full_name: string; designation: string | null } | null;
  permissions: string[];
  scope: { all_companies: boolean; company_ids: string[]; own_only: boolean };
};

const MeCtx = createContext<Me | null>(null);
export const useMe = () => useContext(MeCtx)!;
export const can = (me: Me, p: string) => me.permissions.includes(p);

const NAV = [
  { href: "/", label: "Command Centre", icon: "◎", perm: "dashboard.view" },
  { href: "/assistant/", label: "Executive AI", icon: "✦", perm: "assistant.use" },
  { href: "/org/", label: "Organisation", icon: "⌘", perm: "dashboard.view" },
  { href: "/people/", label: "Workforce", icon: "◍", perm: "people.view" },
  { href: "/agents/", label: "AI Agent Factory", icon: "⬡", perm: "agents.view" },
  { href: "/work/", label: "Tasks & Approvals", icon: "☰", perm: "tasks.view" },
  { href: "/hub/", label: "Employee Hub", icon: "▣", perm: "attendance.manage" },
  { href: "/crm/", label: "CRM & Sales", icon: "↗", perm: "crm.view" },
  { href: "/projects/", label: "Projects", icon: "◫", perm: "projects.view" },
  { href: "/finance/", label: "Finance", icon: "₨", perm: "finance.view" },
  { href: "/settings/", label: "Settings & System", icon: "⚙", perm: "tasks.view" },
];

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <circle cx="32" cy="32" r="19" fill="none" stroke="#22d3ee" strokeWidth="3" />
      <circle cx="32" cy="32" r="6" fill="#3b82f6" />
      <g stroke="#3b82f6" strokeWidth="2.5"><line x1="32" y1="9" x2="32" y2="26" /><line x1="32" y1="38" x2="32" y2="55" /><line x1="9" y1="32" x2="26" y2="32" /><line x1="38" y1="32" x2="55" y2="32" /></g>
    </svg>
  );
}

export default function Shell({ children, title, sub, actions }: { children: ReactNode; title: string; sub?: ReactNode; actions?: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [open, setOpen] = useState(false);
  const path = usePathname();
  useEffect(() => { api<Me>("/auth/me").then(setMe).catch(() => {}); }, []);
  if (!me) return <div className="empty" style={{ paddingTop: 120 }}>Loading NES GLOBAL OS…</div>;
  const items = NAV.filter((n) => can(me, n.perm));
  const norm = (p: string) => (p.endsWith("/") ? p : p + "/");
  return (
    <MeCtx.Provider value={me}>
      <div className="shell">
        <nav className={`side ${open ? "open" : ""}`} aria-label="Main">
          <div className="brand"><Logo /><div><b>NES GLOBAL OS</b><span>NADIR E-SKILLS GROUP</span></div></div>
          <div className="nav stack" style={{ gap: 2 }}>
            {items.map((n) => (
              <a key={n.href} href={n.href} className={norm(path) === n.href ? "on" : ""} onClick={() => setOpen(false)}>
                <span style={{ width: 16, textAlign: "center" }}>{n.icon}</span>{n.label}
              </a>
            ))}
          </div>
          <div className="who">
            <div>{me.person?.full_name || me.user.email}</div>
            <div className="faint">{me.role_label}{!me.user.mfa_enabled && <> · <a href="/settings/">enable MFA</a></>}</div>
            <button className="btn sm ghost" style={{ marginTop: 8, paddingLeft: 0 }}
              onClick={async () => { await api("/auth/logout", { method: "POST" }); location.href = "/login/"; }}>Sign out</button>
          </div>
        </nav>
        <main className="main">
          <div className="top">
            <div className="row">
              <button className="btn sm burger" onClick={() => setOpen(!open)} aria-label="Menu">☰</button>
              <div><h1>{title}</h1>{sub && <div className="sub">{sub}</div>}</div>
            </div>
            <div className="row">{actions}</div>
          </div>
          {children}
        </main>
      </div>
    </MeCtx.Provider>
  );
}
