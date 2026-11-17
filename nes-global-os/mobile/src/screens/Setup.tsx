import { useEffect, useState } from "react";
import { Capacitor } from "@capacitor/core";
import { Device } from "./device";
import { api, ApiError, lanServerUrl, normaliseServer, saveLanServer, saveServer, saveToken, serverUrl } from "../api";
import { bioState, store } from "../native";
import { Logo } from "./Logo";

export function Setup({ notice, onReady }: { notice: string | null; onReady: (me: any) => void }) {
  const [step, setStep] = useState<"server" | "login">(serverUrl() ? "login" : "server");
  const [server, setServer] = useState(serverUrl() || "https://");
  const [lan, setLan] = useState(lanServerUrl() || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [needMfa, setNeedMfa] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [warn, setWarn] = useState<string | null>(null);

  useEffect(() => {
    bioState().then((b) => {
      if (!b.secure) setWarn("Set a screen lock (fingerprint, face or PIN) on this phone first. NES Team uses it to protect company data.");
    }).catch(() => {});
  }, []);

  const checkServer = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const url = normaliseServer(server);
      const r = await api<any>("/mobile/config", { base: url, auth: false });
      if (r?.system !== "NES GLOBAL OS") throw new Error("That address is not an NES GLOBAL OS server.");
      await saveServer(url);
      if (lan.trim()) {
        const l = normaliseServer(lan, "http://");
        try {
          await api<any>("/mobile/config", { base: l, auth: false });
        } catch {
          throw new Error("The office address doesn't answer. Connect to the office Wi-Fi to check it, or leave it empty.");
        }
      }
      await saveLanServer(lan.trim());
      setStep("login");
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 0
        ? "Can't reach that address. Check the spelling and that Tailscale is ON on this phone."
        : (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const signIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      let installId = await store.get("install_id");
      if (!installId) {
        installId = crypto.randomUUID();
        await store.set("install_id", installId);
      }
      const r = await api<any>("/mobile/login", {
        auth: false,
        body: { email, password, mfa_code: needMfa ? code : null, device_name: Device.name(), platform: Capacitor.getPlatform(),
                app_version: "1.0.0", install_id: installId },
      });
      await saveToken(r.token, r.name);
      const home = await api<any>("/mobile/home");
      onReady({ name: home.person.name, role: home.role, is_leader: home.is_leader, person_id: home.person.id });
    } catch (e) {
      const d = (e as ApiError).detail;
      if (d?.mfa_required) setNeedMfa(true);
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="center-screen">
      <div className="brand"><Logo size={64} /><b>NES Team</b><span>Nadir E-Skills employee app</span></div>
      {step === "server" ? (
        <form className="card stack" onSubmit={checkServer}>
          {notice && <div className="note">{notice}</div>}
          <h2>Connect to your company</h2>
          <label className="field"><span>Server address</span>
            <input value={server} onChange={(e) => setServer(e.target.value)} inputMode="url" autoCapitalize="none" autoCorrect="off" required />
            <small>Your IT admin gives you this, e.g. https://nes-server.tailXXXX.ts.net — Tailscale must be ON.</small>
          </label>
          <label className="field"><span>Office address (optional)</span>
            <input value={lan} onChange={(e) => setLan(e.target.value)} inputMode="url" autoCapitalize="none" autoCorrect="off" placeholder="http://192.168.1.27" />
            <small>Lets chat and calls keep working on the office Wi-Fi even when the internet is down.</small>
          </label>
          {err && <div className="err">{err}</div>}
          <button className="btn primary block" disabled={busy}>{busy ? "Checking…" : "Continue"}</button>
        </form>
      ) : (
        <form className="card stack" onSubmit={signIn}>
          {notice && <div className="note">{notice}</div>}
          {warn && <div className="warnmsg">{warn}</div>}
          <h2>Sign in</h2>
          <label className="field"><span>Work email</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoCapitalize="none" autoComplete="username" required />
          </label>
          <label className="field"><span>Password</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </label>
          {needMfa && (
            <label className="field"><span>Authenticator code</span>
              <input inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} autoFocus required />
            </label>
          )}
          {err && <div className="err">{err}</div>}
          <button className="btn primary block" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          <button type="button" className="btn block" onClick={() => { setStep("server"); setErr(null); }}>Change server</button>
          <div className="tiny muted">Forgot your password? Ask HR or your manager to reset it.</div>
        </form>
      )}
    </div>
  );
}
