// A friendly device label for the admin's device list (no extra plugin needed).
export const Device = {
  name(): string {
    const ua = navigator.userAgent;
    const m = ua.match(/Android [\d.]+; ([^;)]+?)(?: Build|\))/);
    if (m) return m[1].trim().slice(0, 60);
    if (/Android/i.test(ua)) return "Android phone";
    return "Browser";
  },
};
