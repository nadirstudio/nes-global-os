import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.nadireskills.nesteam",
  appName: "NES Team",
  webDir: "dist",
  android: {
    // The app talks to your own NES server over Tailscale (encrypted). HTTPS via `tailscale serve` is recommended.
    allowMixedContent: true,
  },
  plugins: {
    LocalNotifications: { smallIcon: "ic_stat_icon", iconColor: "#2563EB" },
  },
};

export default config;
