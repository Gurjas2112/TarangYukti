// Android background safety (spec §17.4, Milestone 11). Two tasks, defined at module top level so Android can
// start them with the app closed and the screen off:
//   ty-harbour  geofence around the home harbour (1.5 km): leaving starts trip mode, coming back stops it
//   ty-trip     trip-mode location updates (every 60 s / 100 m, foreground service): each fix is checked on the
//               phone against the bundled border line and marine park, raises a local alert with no network,
//               goes into the SQLite outbox and is synced to channels when online.
// Border and park alerts are critical: no daily budget, no quiet hours; repeats are limited by fences.decide.
import * as Location from "expo-location";
import * as Notifications from "expo-notifications";
import * as TaskManager from "expo-task-manager";

import type { Fix } from "../api/channels";
import { i18n } from "../i18n";
import * as outbox from "../offline/outbox";
import { getItem, setItem } from "../offline/store";
import { decide, fenceCheck, type LocalAlert, type Memory } from "../safety/fences";

export const HARBOUR_TASK = "ty-harbour";
export const TRIP_TASK = "ty-trip";
export const CHANNEL = "critical";
const CONFIG = "ty.trip.config";
const MEMORY = "ty.trip.memory";
export const ACTIVE = "ty.trip.active";
const HARBOUR_RADIUS_M = 1500;

export type TripConfig = { boatId: string; lang: string; harbour: { lat: number; lon: number } };

async function config(): Promise<TripConfig | null> {
  const raw = await getItem(CONFIG);
  return raw ? (JSON.parse(raw) as TripConfig) : null;
}

TaskManager.defineTask(HARBOUR_TASK, async ({ data, error }) => {
  if (error) return;
  const { eventType } = data as { eventType: Location.GeofencingEventType };
  if (eventType === Location.GeofencingEventType.Exit) await startTrip();
  if (eventType === Location.GeofencingEventType.Enter) await stopTrip();
});

TaskManager.defineTask(TRIP_TASK, async ({ data, error }) => {
  if (error) return;
  const { locations } = data as { locations: Location.LocationObject[] };
  await onFixes(
    locations.map((l) => ({
      lat: l.coords.latitude,
      lon: l.coords.longitude,
      recorded_at: new Date(l.timestamp).toISOString(),
      speed_knots: l.coords.speed !== null && l.coords.speed >= 0 ? l.coords.speed * 1.94384 : null,
    })),
  );
});

/** Every fix: on-device fence check → local alert when needed → outbox → sync if online. */
export async function onFixes(fixes: Fix[]): Promise<void> {
  const cfg = await config();
  if (!cfg) return;
  let memory = JSON.parse((await getItem(MEMORY)) ?? "{}") as Memory;
  for (const fix of fixes) {
    await outbox.add(cfg.boatId, fix);
    const r = decide(fenceCheck(fix.lat, fix.lon), memory, Date.parse(fix.recorded_at));
    memory = r.memory;
    for (const a of r.alerts) await notify(a, cfg.lang);
  }
  await setItem(MEMORY, JSON.stringify(memory));
  await outbox.sync();
}

async function notify(a: LocalAlert, lang: string): Promise<void> {
  const t = i18n.getFixedT(lang);
  const km = a.imblKm.toFixed(1);
  const body = a.rule === "park" ? t("local.park.inside") : t(`local.border.${a.level}`, { km });
  await Notifications.scheduleNotificationAsync({
    content: {
      title: t("app.title"),
      body,
      data: { url: "/trip", kind: "local-alert" }, // never coordinates in a notification
      priority: Notifications.AndroidNotificationPriority.MAX,
      sound: "default",
    },
    trigger: { channelId: CHANNEL },
  });
}

export async function startTrip(): Promise<void> {
  const cfg = await config();
  if (!cfg) return;
  if (await Location.hasStartedLocationUpdatesAsync(TRIP_TASK)) return;
  const t = i18n.getFixedT(cfg.lang);
  await Location.startLocationUpdatesAsync(TRIP_TASK, {
    accuracy: Location.Accuracy.Balanced,
    timeInterval: 60_000,
    distanceInterval: 100,
    pausesUpdatesAutomatically: false,
    foregroundService: {
      notificationTitle: t("trip.service.title"),
      notificationBody: t("trip.service.body"),
      killServiceOnDestroy: false,
    },
  });
  await setItem(ACTIVE, new Date().toISOString());
}

export async function stopTrip(): Promise<void> {
  if (await Location.hasStartedLocationUpdatesAsync(TRIP_TASK)) await Location.stopLocationUpdatesAsync(TRIP_TASK);
  await setItem(ACTIVE, "");
  await outbox.sync();
}

/**
 * Turn background safety on (after the user tapped "Turn on alerts" and saw the explanation): foreground then
 * background location permission, the critical alert channel, and the harbour geofence. Returns false when a
 * permission was refused; foreground alerts and server alerts keep working then.
 */
export async function enableBackgroundSafety(cfg: TripConfig): Promise<boolean> {
  const fg = await Location.requestForegroundPermissionsAsync();
  if (fg.status !== "granted") return false;
  await setItem(CONFIG, JSON.stringify(cfg));
  await Notifications.setNotificationChannelAsync(CHANNEL, {
    name: i18n.getFixedT(cfg.lang)("local.channel"),
    importance: Notifications.AndroidImportance.MAX,
    vibrationPattern: [0, 600, 250, 600, 250, 600], // distinct pattern for critical alerts (spec §6.5)
    sound: "default",
    bypassDnd: true,
  });
  const bg = await Location.requestBackgroundPermissionsAsync(); // Android shows "Allow all the time" in settings
  if (bg.status !== "granted") return false;
  if (await Location.hasStartedGeofencingAsync(HARBOUR_TASK)) await Location.stopGeofencingAsync(HARBOUR_TASK);
  await Location.startGeofencingAsync(HARBOUR_TASK, [
    {
      identifier: "home",
      latitude: cfg.harbour.lat,
      longitude: cfg.harbour.lon,
      radius: HARBOUR_RADIUS_M,
      notifyOnEnter: true,
      notifyOnExit: true,
    },
  ]);
  return true;
}

export async function backgroundSafetyOn(): Promise<boolean> {
  return TaskManager.isTaskRegisteredAsync(HARBOUR_TASK);
}

export async function tripActiveSince(): Promise<string | null> {
  return (await getItem(ACTIVE)) || null;
}
