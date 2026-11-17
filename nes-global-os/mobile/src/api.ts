// API client for the NES GLOBAL OS server. The token lives in app-private storage and is sent as a Bearer header.
import { store } from "./native";

let server = "";      // main address (Tailscale HTTPS), works anywhere
let lanServer = "";   // optional office address (e.g. http://192.168.1.27), works on office Wi-Fi without internet
let active = "";      // the one currently in use
let token = "";
let onSignedOut: (reason: string, wipe: boolean) => void = () => {};

export class ApiError extends Error {
  status: number;
  detail: any;
  constructor(status: number, message: string, detail?: any) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export async function loadSession() {
  server = (await store.get("server")) || "";
  lanServer = (await store.get("server_lan")) || "";
  active = server;
  token = (await store.get("token")) || "";
  return { server, token, name: (await store.get("name")) || "" };
}

async function reachable(base: string, ms = 1500): Promise<boolean> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(`${base}/api/mobile/config`, { signal: ctrl.signal });
    return r.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(t);
  }
}

/** Prefer the office address when it answers (keeps working without internet), else the main address. */
export async function pickServer(): Promise<string> {
  if (lanServer && (await reachable(lanServer))) active = lanServer;
  else active = server || lanServer;
  return active;
}

export function activeServer() {
  return active || server;
}

export function lanServerUrl() {
  return lanServer;
}

export async function saveLanServer(url: string) {
  lanServer = url ? normaliseServer(url, "http://") : "";
  if (lanServer) await store.set("server_lan", lanServer);
  else await store.remove("server_lan");
  await pickServer();
}

export function wsUrl(path: string) {
  return activeServer().replace(/^http/, "ws") + path;
}

export function setSignedOutHandler(fn: (reason: string, wipe: boolean) => void) {
  onSignedOut = fn;
}

export function serverUrl() {
  return server;
}

export function fileBase() {
  return activeServer();
}

export function normaliseServer(input: string, scheme = "https://") {
  let s = input.trim().replace(/\/+$/, "");
  if (s && !/^https?:\/\//i.test(s)) s = scheme + s;
  return s;
}

export async function saveServer(url: string) {
  server = normaliseServer(url);
  active = server;
  await store.set("server", server);
}

export async function saveToken(t: string, name: string) {
  token = t;
  await store.set("token", t);
  await store.set("name", name);
}

export async function clearSession(wipe = false) {
  token = "";
  if (wipe) {
    await store.wipe(); // remote wipe: remove everything the app stored, including the server address
    server = "";
    lanServer = "";
    active = "";
  } else {
    await store.remove("token");
    await store.remove("name");
  }
}

function message(detail: any, status: number): string {
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail)) return detail.map((e: any) => e.msg).join("; ");
  if (status === 0) return "Can't reach the NES server. Check that Tailscale is connected and you have internet.";
  return `Something went wrong (${status})`;
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; base?: string; auth?: boolean } = {}): Promise<T> {
  try {
    return await request<T>(path, opts);
  } catch (e) {
    // Network failure on one address → switch to the other (office ↔ Tailscale) and retry once.
    if (e instanceof ApiError && e.status === 0 && !opts.base && server && lanServer) {
      const before = active;
      await pickServer();
      if (active === before) active = before === lanServer ? server : lanServer;
      return await request<T>(path, opts);
    }
    throw e;
  }
}

async function request<T>(path: string, opts: { method?: string; body?: unknown; base?: string; auth?: boolean }): Promise<T> {
  const base = opts.base ?? activeServer();
  if (!base) throw new ApiError(0, "Server address is not set");
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["content-type"] = "application/json";
  if (opts.auth !== false && token) headers["authorization"] = `Bearer ${token}`;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 30000);
  let res: Response;
  try {
    res = await fetch(`${base}/api${path}`, {
      method: opts.method || (opts.body !== undefined ? "POST" : "GET"),
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: ctrl.signal,
    });
  } catch {
    throw new ApiError(0, message(null, 0));
  } finally {
    clearTimeout(timer);
  }
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const detail = data?.detail;
    if (res.status === 401 && opts.auth !== false && token) {
      const revoked = !!detail?.device_revoked;
      await clearSession(!!detail?.wipe);
      onSignedOut(revoked ? message(detail, 401) : "Your session ended. Please sign in again.", !!detail?.wipe);
    }
    throw new ApiError(res.status, message(detail, res.status), detail);
  }
  return data as T;
}

// ---------------------------------------------------------------- formatting
export const fmt = {
  date: (s?: string | null) => (s ? new Date(s.length === 10 ? s + "T00:00:00" : s).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "—"),
  day: (s: string) => new Date(s + "T00:00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }),
  time: (s?: string | null) => (s ? new Date(s).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Karachi" }) : "—"),
  ago: (s: string) => {
    const m = Math.round((Date.now() - new Date(s).getTime()) / 60000);
    if (m < 1) return "now";
    if (m < 60) return `${m}m`;
    if (m < 1440) return `${Math.round(m / 60)}h`;
    return new Date(s).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  },
  label: (s?: string | null) => (s ? s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : ""),
  initials: (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase(),
};
