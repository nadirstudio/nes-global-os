// Thin wrappers around device features. In a desktop browser (preview/testing) they fall back to web APIs.
import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";
import { Geolocation } from "@capacitor/geolocation";
import { Camera, CameraResultType, CameraSource } from "@capacitor/camera";
import { Browser } from "@capacitor/browser";
import { LocalNotifications } from "@capacitor/local-notifications";
import { BiometricAuth, BiometryError, BiometryErrorType } from "@aparajita/capacitor-biometric-auth";

export const isNative = Capacitor.isNativePlatform();

// ---------------------------------------------------------------- storage (app-private)
export const store = {
  get: async (key: string) => (await Preferences.get({ key })).value,
  set: (key: string, value: string) => Preferences.set({ key, value }),
  remove: (key: string) => Preferences.remove({ key }),
  wipe: () => Preferences.clear(),
};

// ---------------------------------------------------------------- location
export type Fix = { lat: number; lng: number; accuracy: number };

export async function getLocation(): Promise<Fix> {
  if (isNative) {
    let perm = await Geolocation.checkPermissions();
    if (perm.location !== "granted") perm = await Geolocation.requestPermissions({ permissions: ["location"] });
    if (perm.location !== "granted") throw new Error("Location permission is off. Allow it in Settings → Apps → NES Team → Permissions.");
  }
  try {
    const p = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 25000, maximumAge: 0 });
    return { lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy };
  } catch (e) {
    const msg = (e as Error).message || "";
    if (/denied|permission/i.test(msg)) throw new Error("Location permission is off. Allow it for NES Team and try again.");
    if (/timeout|unavailable/i.test(msg)) throw new Error("Couldn't get your location. Turn on GPS/location and try again.");
    throw new Error("Couldn't get your location: " + msg);
  }
}

// ---------------------------------------------------------------- camera
/** Opens the camera and returns a data URL (base64) of the photo taken. */
export async function takePhoto(): Promise<string> {
  if (isNative) {
    let perm = await Camera.checkPermissions();
    if (perm.camera !== "granted") perm = await Camera.requestPermissions({ permissions: ["camera"] });
    if (perm.camera !== "granted") throw new Error("Camera permission is off. Allow it in Settings → Apps → NES Team → Permissions.");
  }
  try {
    const photo = await Camera.getPhoto({
      resultType: CameraResultType.DataUrl,
      source: CameraSource.Camera,
      quality: 80,
    });
    if (!photo.dataUrl) throw new Error("No photo captured.");
    return photo.dataUrl;
  } catch (e) {
    const msg = (e as Error).message || "";
    if (/denied|permission/i.test(msg)) throw new Error("Camera permission is off. Allow it for NES Team and try again.");
    if (/cancel/i.test(msg)) throw new Error("Photo capture cancelled.");
    throw new Error("Couldn't take photo: " + msg);
  }
}

// ---------------------------------------------------------------- biometrics
export type BioState = { available: boolean; secure: boolean; label: string };

export async function bioState(): Promise<BioState> {
  if (!isNative) return { available: true, secure: true, label: "Fingerprint (preview)" };
  const r = await BiometricAuth.checkBiometry();
  const label = r.biometryType === 3 || r.biometryType === 4 ? "Face unlock" : "Fingerprint";
  return { available: r.isAvailable, secure: r.deviceIsSecure, label };
}

/** Returns true when the phone owner confirmed with fingerprint/face (or the phone PIN as a fallback). */
export async function confirmIdentity(reason: string): Promise<boolean> {
  if (!isNative) return window.confirm(`Browser preview — simulated fingerprint.\n\n${reason}`);
  try {
    await BiometricAuth.authenticate({
      reason,
      cancelTitle: "Cancel",
      allowDeviceCredential: true,
      androidTitle: "NES Team",
      androidSubtitle: reason,
      androidConfirmationRequired: false,
    });
    return true;
  } catch (e) {
    if (e instanceof BiometryError && e.code === BiometryErrorType.userCancel) return false;
    if (e instanceof BiometryError && e.code === BiometryErrorType.biometryLockout)
      throw new Error("Too many attempts. Unlock your phone first, then try again.");
    throw new Error((e as Error).message || "Identity check failed");
  }
}

// ---------------------------------------------------------------- notifications (shown while the app is running)
let notifId = 1;
let notifAllowed: boolean | null = null;

export async function notify(title: string, body: string) {
  try {
    if (isNative) {
      if (notifAllowed === null) notifAllowed = (await LocalNotifications.requestPermissions()).display === "granted";
      if (!notifAllowed) return;
      await LocalNotifications.schedule({ notifications: [{ id: notifId++, title, body }] });
    } else if ("Notification" in window && Notification.permission === "granted") {
      new Notification(title, { body });
    }
  } catch {
    /* notifications are best-effort */
  }
}

// ---------------------------------------------------------------- links
export async function openUrl(url: string) {
  if (isNative) await Browser.open({ url });
  else window.open(url, "_blank", "noopener");
}

export function telLink(phone?: string | null) {
  return phone ? "tel:" + phone.replace(/[^\d+]/g, "") : undefined;
}

export function waLink(phone?: string | null) {
  if (!phone) return undefined;
  let d = phone.replace(/\D/g, "");
  if (d.startsWith("0") && d.length === 11) d = "92" + d.slice(1);
  return "https://wa.me/" + d;
}
