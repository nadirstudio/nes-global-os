// Same-origin API client. The session lives in an httpOnly cookie; no token or API key ever touches JS.
export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function message(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    if (typeof d.message === "string") return d.message;
    if (Array.isArray(detail)) {
      return detail.map((e: { loc?: unknown[]; msg?: string }) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ");
    }
  }
  return `Request failed (${status})`;
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: opts.method || (opts.body !== undefined ? "POST" : "GET"),
    credentials: "same-origin",
    headers: opts.body !== undefined ? { "content-type": "application/json" } : undefined,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail;
    if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/login")) {
      window.location.href = "/login/";
    }
    throw new ApiError(res.status, message(detail, res.status), detail);
  }
  return data as T;
}

export const fmt = {
  pkr: (n: number | null | undefined) => (n == null ? "—" : `PKR ${Math.round(n).toLocaleString("en-PK")}`),
  num: (n: number | null | undefined) => (n == null ? "—" : n.toLocaleString("en-PK")),
  usd: (n: number | null | undefined) => (n == null ? "—" : `$${n.toFixed(n < 1 ? 4 : 2)}`),
  date: (s: string | null | undefined) =>
    s ? new Date(s).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "Asia/Karachi" }) : "—",
  dt: (s: string | null | undefined) =>
    s ? new Date(s).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Karachi" }) : "—",
  ago: (s: string) => {
    const m = Math.round((Date.now() - new Date(s).getTime()) / 60000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    if (m < 1440) return `${Math.round(m / 60)}h ago`;
    return `${Math.round(m / 1440)}d ago`;
  },
  label: (s: string | null | undefined) => (s ? s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "—"),
};
