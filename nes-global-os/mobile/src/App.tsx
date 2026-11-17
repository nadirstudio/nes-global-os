import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { App as CapApp } from "@capacitor/app";
import { api, clearSession, loadSession, pickServer, setSignedOutHandler } from "./api";
import { calls } from "./calls";
import { CallLayer } from "./screens/CallLayer";
import { confirmIdentity, isNative, notify } from "./native";
import { Setup } from "./screens/Setup";
import { Home } from "./screens/Home";
import { Leave } from "./screens/Leave";
import { Shifts } from "./screens/Shifts";
import { TaskDetail, Tasks } from "./screens/Tasks";
import { Approvals } from "./screens/Approvals";
import { ChatList, Conversation } from "./screens/Chat";
import { People, PersonCard } from "./screens/People";
import { News } from "./screens/News";
import { DocView, Docs } from "./screens/Docs";
import { Assistant } from "./screens/Assistant";
import { Attendance, More } from "./screens/More";
import { Logo } from "./screens/Logo";

export type Route = { name: string; params?: any };
type Counts = { unread_chat: number; unread_news: number; pending_approvals: number; missed_calls: number };
type Me = { name: string; role: string; is_leader: boolean; person_id: string };

type Ctx = {
  me: Me;
  counts: Counts;
  push: (r: Route) => void;
  back: () => void;
  setTab: (t: string) => void;
  refreshCounts: () => void;
  signOut: () => Promise<void>;
  setMe: (m: Me) => void;
};
const AppCtx = createContext<Ctx>(null as any);
export const useApp = () => useContext(AppCtx);

const TABS = [
  { id: "home", icon: "⌂", label: "Home" },
  { id: "tasks", icon: "☑", label: "Tasks" },
  { id: "chat", icon: "💬", label: "Chat" },
  { id: "people", icon: "👥", label: "People" },
  { id: "more", icon: "☰", label: "More" },
];
const LOCK_AFTER_MS = 2 * 60 * 1000;

export default function App() {
  const [phase, setPhase] = useState<"boot" | "setup" | "locked" | "ready">("boot");
  const [notice, setNotice] = useState<string | null>(null);
  const [me, setMe] = useState<Me>({ name: "", role: "", is_leader: false, person_id: "" });
  const [tab, setTabState] = useState("home");
  const [stack, setStack] = useState<Route[]>([]);
  const [counts, setCounts] = useState<Counts>({ unread_chat: 0, unread_news: 0, pending_approvals: 0, missed_calls: 0 });
  const lastBg = useRef<number>(0);
  const lastSync = useRef<string | null>(null);
  const prevChat = useRef(0);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  // ------------------------------------------------ boot
  useEffect(() => {
    setSignedOutHandler((reason, wipe) => {
      calls.disconnect();
      setNotice(wipe ? `${reason} Company data on this phone has been removed.` : reason);
      setStack([]);
      setTabState("home");
      setPhase("setup");
    });
    (async () => {
      const s = await loadSession();
      await pickServer();
      if (s.server && s.token) {
        setMe((m) => ({ ...m, name: s.name }));
        setPhase("locked");
      } else setPhase("setup");
    })();
  }, []);

  // ------------------------------------------------ biometric lock on open / resume
  const unlock = useCallback(async () => {
    try {
      const ok = await confirmIdentity("Unlock NES Team");
      if (ok) setPhase("ready");
    } catch (e) {
      setNotice((e as Error).message);
    }
  }, []);
  useEffect(() => { if (phase === "locked") unlock(); }, [phase, unlock]);
  useEffect(() => {
    if (!isNative) return;
    const sub = CapApp.addListener("appStateChange", ({ isActive }) => {
      if (!isActive) lastBg.current = Date.now();
      else {
        // back in the foreground: re-check office vs Tailscale address and the call connection
        pickServer().then(() => { if (phaseRef.current === "ready") calls.connect(); });
        if (phaseRef.current === "ready" && lastBg.current && Date.now() - lastBg.current > LOCK_AFTER_MS && calls.getState().phase === "idle") setPhase("locked");
      }
    });
    return () => { sub.then((s) => s.remove()); };
  }, []);

  // ------------------------------------------------ navigation
  const push = useCallback((r: Route) => setStack((s) => [...s, r]), []);
  const back = useCallback(() => setStack((s) => s.slice(0, -1)), []);
  const setTab = useCallback((t: string) => { setStack([]); setTabState(t); }, []);
  useEffect(() => { window.scrollTo(0, 0); }, [stack.length, tab]);
  const stackRef = useRef(stack);
  stackRef.current = stack;
  const tabRef = useRef(tab);
  tabRef.current = tab;
  useEffect(() => {
    if (!isNative) return;
    const sub = CapApp.addListener("backButton", () => {
      if (stackRef.current.length) back();
      else if (tabRef.current !== "home") setTab("home");
      else CapApp.minimizeApp();
    });
    return () => { sub.then((s) => s.remove()); };
  }, [back, setTab]);

  // ------------------------------------------------ live counts + notifications (while the app is open)
  const refreshCounts = useCallback(async () => {
    if (phaseRef.current !== "ready") return;
    try {
      const q = lastSync.current ? `?since=${encodeURIComponent(lastSync.current)}` : "";
      const r = await api<any>(`/mobile/sync${q}`);
      if (lastSync.current) {
        for (const n of r.new_urgent) notify(`📢 ${n.title}`, n.body.slice(0, 120));
        if (r.unread_chat > prevChat.current) notify("NES Team", `You have ${r.unread_chat} unread message${r.unread_chat > 1 ? "s" : ""}`);
      }
      prevChat.current = r.unread_chat;
      lastSync.current = r.server_time;
      setCounts({ unread_chat: r.unread_chat, unread_news: r.unread_news, pending_approvals: r.pending_approvals, missed_calls: r.missed_calls || 0 });
    } catch {
      /* offline: keep last counts */
    }
  }, []);
  useEffect(() => {
    if (phase === "ready") calls.connect();
  }, [phase]);
  useEffect(() => {
    if (phase !== "ready") return;
    refreshCounts();
    const t = setInterval(refreshCounts, 30000);
    return () => clearInterval(t);
  }, [phase, refreshCounts]);

  const signOut = useCallback(async () => {
    calls.disconnect();
    try { await api("/mobile/logout", { method: "POST" }); } catch { /* ignore */ }
    await clearSession(false);
    setStack([]);
    setTabState("home");
    setNotice("You have signed out.");
    setPhase("setup");
  }, []);

  // ------------------------------------------------ render
  if (phase === "boot") return <div className="center-screen"><div className="brand"><Logo size={64} /><b>NES Team</b></div></div>;
  if (phase === "setup")
    return <Setup notice={notice} onReady={(m) => { setMe(m); setNotice(null); setPhase("ready"); }} />;
  if (phase === "locked")
    return (
      <div className="center-screen">
        <div className="brand"><Logo size={64} /><b>NES Team</b><span>{me.name ? `Welcome back, ${me.name.split(" ")[0]}` : "Locked"}</span></div>
        <div className="card stack">
          {notice && <div className="err">{notice}</div>}
          <button className="btn primary block" onClick={unlock}>🔒 Unlock with fingerprint</button>
          <button className="btn block" onClick={signOut}>Sign out</button>
        </div>
      </div>
    );

  const ctx: Ctx = { me, counts, push, back, setTab, refreshCounts, signOut, setMe };
  const top = stack[stack.length - 1];
  return (
    <AppCtx.Provider value={ctx}>
      {top ? <Pushed route={top} /> : <TabRoot tab={tab} />}
      <CallLayer />
      {(!top || !["conversation", "assistant"].includes(top.name)) && (
        <nav className="nav" aria-label="Main">
          {TABS.map((t) => {
            const badge = t.id === "chat" ? counts.unread_chat + counts.missed_calls : t.id === "more" ? counts.unread_news + counts.pending_approvals : 0;
            return (
              <button key={t.id} className={tab === t.id && !top ? "on" : ""} onClick={() => setTab(t.id)}>
                <span className="ni">{t.icon}</span>{t.label}
                {badge > 0 && <span className="dotcount">{badge > 99 ? "99+" : badge}</span>}
              </button>
            );
          })}
        </nav>
      )}
    </AppCtx.Provider>
  );
}

function TabRoot({ tab }: { tab: string }) {
  switch (tab) {
    case "tasks": return <Tasks />;
    case "chat": return <ChatList />;
    case "people": return <People />;
    case "more": return <More />;
    default: return <Home />;
  }
}

function Pushed({ route }: { route: Route }) {
  const p = route.params || {};
  switch (route.name) {
    case "leave": return <Leave />;
    case "shifts": return <Shifts />;
    case "task": return <TaskDetail id={p.id} />;
    case "approvals": return <Approvals />;
    case "conversation": return <Conversation id={p.id} title={p.title} />;
    case "person": return <PersonCard person={p.person} />;
    case "news": return <News />;
    case "docs": return <Docs />;
    case "doc": return <DocView id={p.id} />;
    case "assistant": return <Assistant initial={p.q} />;
    case "attendance": return <Attendance />;
    default: return <Home />;
  }
}
