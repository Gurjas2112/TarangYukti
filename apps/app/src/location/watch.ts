// Web build: navigator.geolocation.watchPosition while the page is open, at most one fix a minute (spec §6.8).
export type Coords = { lat: number; lon: number; speedKnots: number | null; at: string };

export async function watch(onFix: (c: Coords) => void): Promise<() => void> {
  if (typeof navigator === "undefined" || !navigator.geolocation) throw new Error("no geolocation");
  let last = 0;
  const id = navigator.geolocation.watchPosition(
    (p) => {
      if (p.timestamp - last < 60_000) return;
      last = p.timestamp;
      onFix({
        lat: p.coords.latitude,
        lon: p.coords.longitude,
        speedKnots: p.coords.speed !== null && p.coords.speed >= 0 ? p.coords.speed * 1.94384 : null,
        at: new Date(p.timestamp).toISOString(),
      });
    },
    () => undefined,
    { enableHighAccuracy: true, maximumAge: 30_000, timeout: 60_000 },
  );
  return () => navigator.geolocation.clearWatch(id);
}
