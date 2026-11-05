// On-device fences (spec §17.4): distance to the India–Sri Lanka border line (IMBL) and the marine park, for
// every position fix, with no network. Same layer files as the server (data/layers → src/safety/layers, kept
// identical by a test) and the same rules as services/mcp tools/geo.py fence_check:
//   ring = "beyond" (past the line) · "alarm" ≤ 2 km · "warning" ≤ 5 km · "clear".
import { booleanPointInPolygon } from "@turf/boolean-point-in-polygon";
import { lineString, point, polygon } from "@turf/helpers";
import { pointToLineDistance } from "@turf/point-to-line-distance";

import imblJson from "./layers/imbl.json";
import mpaJson from "./layers/mpa.json";

export type Ring = "clear" | "warning" | "alarm" | "beyond";
export type Fence = { imblKm: number; ring: Ring; side: "india" | "beyond_imbl"; inMpa: boolean };
export type Fix = { lat: number; lon: number; at: string; speedKnots?: number | null };

export const WARNING_KM = 5;
export const ALARM_KM = 2;

type Coords = [number, number][];
const imblCoords = (imblJson as unknown as { features: { geometry: { coordinates: Coords } }[] }).features[0].geometry
  .coordinates;
const imbl = lineString(imblCoords);

// India is on the north-west (left) side of the SW → NE line: close a polygon around that side, exactly as the
// server does (services/mcp tarangyukti/layers.py).
const [[x0, y0], [x1]] = [imblCoords[0], imblCoords[imblCoords.length - 1]];
const indiaSide = polygon([[...imblCoords, [x1, 30], [60, 30], [60, y0], [x0, y0], imblCoords[0]]]);

type Mpa = { features: { geometry: { type: "MultiPolygon"; coordinates: number[][][][] } }[] };
const mpa = (mpaJson as unknown as Mpa).features[0].geometry;

export function ringFor(km: number, beyond: boolean): Ring {
  if (beyond) return "beyond";
  if (km <= ALARM_KM) return "alarm";
  if (km <= WARNING_KM) return "warning";
  return "clear";
}

export function fenceCheck(lat: number, lon: number): Fence {
  const p = point([lon, lat]);
  const imblKm = pointToLineDistance(p, imbl, { units: "kilometers" });
  const beyond = !booleanPointInPolygon(p, indiaSide);
  return {
    imblKm,
    ring: ringFor(imblKm, beyond),
    side: beyond ? "beyond_imbl" : "india",
    inMpa: booleanPointInPolygon(p, mpa),
  };
}

// ── alert decisions ────────────────────────────────────────────────────────────────────────────────────

export type Rule = "border" | "park";
export type LocalAlert = { rule: Rule; level: "warning" | "alarm" | "beyond" | "inside"; imblKm: number };
export type Memory = Partial<Record<Rule, { level: string; at: number }>>;

const LEVEL_RANK: Record<string, number> = { warning: 1, alarm: 2, beyond: 3, inside: 1 };
export const REPEAT_MS = 2 * 60 * 60 * 1000; // the same rule repeats at most once per 2 h (spec §6.6)

/**
 * Which local alerts to raise for this fix. Border and park alerts are critical (prompt §10.7): no daily budget
 * and no quiet hours. The same rule and level repeats at most once per 2 h; a higher level always fires at once.
 * Returns the alerts and the updated memory.
 */
export function decide(f: Fence, memory: Memory, now: number): { alerts: LocalAlert[]; memory: Memory } {
  const out: LocalAlert[] = [];
  const next: Memory = { ...memory };
  const consider = (rule: Rule, level: LocalAlert["level"] | null) => {
    if (level === null) {
      delete next[rule]; // back in the clear: the next approach alerts again
      return;
    }
    const last = memory[rule];
    const rises = !last || LEVEL_RANK[level] > LEVEL_RANK[last.level];
    const stale = !last || now - last.at >= REPEAT_MS;
    if (rises || (last.level === level && stale)) {
      out.push({ rule, level, imblKm: f.imblKm });
      next[rule] = { level, at: now };
    }
  };
  consider("border", f.ring === "clear" ? null : f.ring);
  consider("park", f.inMpa ? "inside" : null);
  return { alerts: out, memory: next };
}
