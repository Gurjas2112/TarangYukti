// Web build: service worker + Web Push (VAPID) → channels /push/subscribe (kind "web").
// The permission prompt appears only after the user taps "Turn on alerts".
import { api } from "../api/channels";
import { getEnv } from "../env";

function b64ToBytes(b64: string): Uint8Array<ArrayBuffer> {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return null;
  return navigator.serviceWorker.register("/sw.js");
}

export async function registerPush(token: string): Promise<boolean> {
  const key = getEnv().VAPID_PUBLIC_KEY;
  if (!key || typeof Notification === "undefined") return false;
  const reg = await registerServiceWorker();
  if (!reg || !("pushManager" in reg)) return false;
  if ((await Notification.requestPermission()) !== "granted") return false;
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(key) });
  const json = sub.toJSON();
  await api.subscribe(token, {
    kind: "web",
    endpoint: sub.endpoint,
    p256dh: json.keys?.p256dh,
    auth: json.keys?.auth,
    user_agent: navigator.userAgent.slice(0, 300),
  });
  return true;
}

export function pushUrl(): string | null {
  return null; // the service worker opens the URL itself (public/sw.js)
}
