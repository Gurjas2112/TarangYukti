// Android, app open: foreground location every 60 s (trip mode in the background is Milestone 11).
import * as Location from "expo-location";

export type Coords = { lat: number; lon: number; speedKnots: number | null; at: string };

export async function watch(onFix: (c: Coords) => void): Promise<() => void> {
  const perm = await Location.requestForegroundPermissionsAsync();
  if (perm.status !== "granted") throw new Error("location permission denied");
  const sub = await Location.watchPositionAsync(
    { accuracy: Location.Accuracy.Balanced, timeInterval: 60_000, distanceInterval: 100 },
    (p) =>
      onFix({
        lat: p.coords.latitude,
        lon: p.coords.longitude,
        speedKnots: p.coords.speed !== null && p.coords.speed >= 0 ? p.coords.speed * 1.94384 : null,
        at: new Date(p.timestamp).toISOString(),
      }),
  );
  return () => sub.remove();
}
