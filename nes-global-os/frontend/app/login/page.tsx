"use client";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Logo } from "@/components/Shell";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [needMfa, setNeedMfa] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api<{ role: string }>("/auth/login", { body: { email, password, mfa_code: needMfa ? code : null } });
      location.href = ["employee", "intern", "freelancer"].includes(r.role) ? "/work/" : "/";
    } catch (e) {
      const d = (e as ApiError).detail as { mfa_required?: boolean } | undefined;
      if (d?.mfa_required) setNeedMfa(true);
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 16 }}>
      <form onSubmit={submit} className="card stack" style={{ width: "min(400px, 100%)", padding: 28, gap: 14 }}>
        <div className="row" style={{ gap: 12 }}>
          <Logo size={40} />
          <div>
            <div style={{ fontWeight: 700, letterSpacing: ".14em" }}>NES GLOBAL OS</div>
            <div className="faint small">NADIR E-SKILLS (SMC-PRIVATE) LIMITED</div>
          </div>
        </div>
        <label className="f">Email<input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label className="f">Password<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        {needMfa && (
          <label className="f">Authenticator code
            <input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} autoFocus required />
          </label>
        )}
        {err && <div className="err">{err}</div>}
        <button className="btn primary" disabled={busy} style={{ justifyContent: "center", padding: 10 }}>{busy ? "Signing in…" : "Sign in"}</button>
        <div className="faint small">Accounts are issued by the CEO. Forgot your password? Ask an administrator to reset it.</div>
      </form>
    </div>
  );
}
