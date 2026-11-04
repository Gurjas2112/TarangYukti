// Live position while the app is open (prompt §15 Milestone 8): one fix a minute to channels /positions, only for a
// signed-in fisher who turned alerts on (location consent). Positions inside the prototype region only; the server
// opens and closes trips and raises border alerts. The last answer is shared with the Trip tab.
import { createContext, type ReactNode, useContext, useEffect, useState } from "react";
import { Platform } from "react-native";

import { api, type PositionsResult } from "../api/channels";
import { useSession } from "../auth/supabase";
import { usePrefs } from "../state/prefs";
import { watch } from "./watch";

const REGION = { latMin: 8.0, latMax: 10.5, lonMin: 78.0, lonMax: 80.5 };

type Live = { last: PositionsResult | null; error: "outside" | "network" | "permission" | null; active: boolean };
const LiveContext = createContext<Live>({ last: null, error: null, active: false });

export function inRegion(lat: number, lon: number): boolean {
  return lat >= REGION.latMin && lat <= REGION.latMax && lon >= REGION.lonMin && lon <= REGION.lonMax;
}

export function LiveTracking({ boatId, children }: { boatId: string | null; children: ReactNode }) {
  const { prefs } = usePrefs();
  const { session } = useSession();
  const token = session?.access_token ?? null;
  const [live, setLive] = useState<Live>({ last: null, error: null, active: false });
  const enabled = Boolean(prefs.alertsOn && token && boatId);

  useEffect(() => {
    if (!enabled || !token || !boatId) return;
    let stop: (() => void) | undefined;
    let alive = true;
    watch(async (c) => {
      if (!inRegion(c.lat, c.lon)) {
        setLive((l) => ({ ...l, error: "outside" }));
        return;
      }
      try {
        const r = await api.positions(token, boatId, Platform.OS === "web" ? "web_live" : "mobile_app", [
          { lat: c.lat, lon: c.lon, recorded_at: c.at, speed_knots: c.speedKnots },
        ]);
        if (alive) setLive({ last: r, error: null, active: true });
      } catch {
        if (alive) setLive((l) => ({ ...l, error: "network" }));
      }
    })
      .then((s) => {
        stop = s;
        if (alive) setLive((l) => ({ ...l, active: true }));
      })
      .catch(() => {
        if (alive) setLive((l) => ({ ...l, error: "permission" }));
      });
    return () => {
      alive = false;
      stop?.();
    };
  }, [enabled, token, boatId]);

  return <LiveContext.Provider value={live}>{children}</LiveContext.Provider>;
}

export const useLive = () => useContext(LiveContext);
