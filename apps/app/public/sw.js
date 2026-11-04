// apps/app/public/sw.js — web build only (spec §6.8): show pushes, open them, keep the last brief offline.
// Push payloads are { id, kind, title, body, url } — never coordinates.
const BRIEF_CACHE = "brief";
const SHELL_CACHE = "shell-v1";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL_CACHE).then((c) => c.addAll(["/", "/manifest.json", "/icon-192.png"])));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (e) => {
  const d = e.data ? e.data.json() : {};
  const kind = d.kind || "alert";
  e.waitUntil(
    Promise.all([
      self.registration.showNotification(d.title || "Kadal Mitra", {
        body: d.body || "",
        tag: kind,
        renotify: kind === "alert",
        requireInteraction: kind === "alert",
        data: { url: d.url || "/" },
        icon: "/icon-192.png",
      }),
      kind === "brief" && d.url ? caches.open(BRIEF_CACHE).then((c) => c.add(d.url)) : null,
    ]),
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(self.clients.openWindow(url));
});

self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;
  const path = new URL(e.request.url).pathname;
  // offline: the saved brief page, else the app shell (the app shows the saved card from localStorage)
  e.respondWith(
    fetch(e.request).catch(async () => {
      if (path.startsWith("/brief")) {
        const hit = await caches.match(e.request, { cacheName: BRIEF_CACHE });
        if (hit) return hit;
      }
      return (await caches.match("/", { cacheName: SHELL_CACHE })) || Response.error();
    }),
  );
});
