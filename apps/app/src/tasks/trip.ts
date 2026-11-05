// Web build: background geofencing and trip mode exist only on Android (trip.native.ts). Same functions, no-ops.
import type { Fix } from "../api/channels";

export type TripConfig = { boatId: string; lang: string; harbour: { lat: number; lon: number } };

export async function onFixes(_fixes: Fix[]): Promise<void> {}
export async function startTrip(): Promise<void> {}
export async function stopTrip(): Promise<void> {}
export async function enableBackgroundSafety(_cfg: TripConfig): Promise<boolean> {
  return false;
}
export async function backgroundSafetyOn(): Promise<boolean> {
  return false;
}
export async function tripActiveSince(): Promise<string | null> {
  return null;
}
