// On-device fences (Milestone 11, spec §16 Mobile): the phone agrees with the server on every fixture point.
import { describe, expect, it } from "@jest/globals";
import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";

import { ALARM_KM, decide, fenceCheck, REPEAT_MS, WARNING_KM } from "../src/safety/fences";
import fixtures from "./fixtures/fences.json";

const repo = path.resolve(__dirname, "../../..");
const sha = (p: string) => createHash("sha256").update(fs.readFileSync(p)).digest("hex");

describe("fences", () => {
  it("bundles exactly the server's layer files", () => {
    expect(sha(path.join(repo, "apps/app/src/safety/layers/imbl.json"))).toBe(sha(path.join(repo, "data/layers/imbl.geojson")));
    expect(sha(path.join(repo, "apps/app/src/safety/layers/mpa.json"))).toBe(sha(path.join(repo, "data/layers/mpa_gom.geojson")));
    expect(sha(path.join(repo, "apps/app/src/safety/layers/land.json"))).toBe(sha(path.join(repo, "data/layers/land.geojson")));
  });

  it.each(fixtures.points)("agrees with the server at $lat, $lon", (p) => {
    const f = fenceCheck(p.lat, p.lon);
    // Within 50 m of the server (plus its 0.1 km rounding) wherever alerts happen (≤ 10 km from the line).
    // Farther out Turf's sphere and the server's UTM projection drift apart by ~0.4 %, which decides nothing.
    const tolerance = p.imbl_km <= 10 ? 0.05 + 0.05 : p.imbl_km * 0.005 + 0.05;
    expect(Math.abs(f.imblKm - p.imbl_km)).toBeLessThanOrEqual(tolerance);
    expect(f.side).toBe(p.side);
    expect(f.inMpa).toBe(p.in_mpa);
    const onEdge = [WARNING_KM, ALARM_KM].some((t) => Math.abs(p.imbl_km - t) < 0.15);
    if (!onEdge) expect(f.ring).toBe(p.ring);
  });
});

describe("local alert decisions", () => {
  const at = (km: number, ring: "clear" | "warning" | "alarm" | "beyond", inMpa = false) => ({
    imblKm: km,
    ring,
    side: ring === "beyond" ? ("beyond_imbl" as const) : ("india" as const),
    inMpa,
  });
  const t0 = Date.UTC(2026, 10, 5, 4, 0);

  it("warns at 5 km, alarms at 2 km at once, and does not repeat inside 2 h", () => {
    let r = decide(at(4.8, "warning"), {}, t0);
    expect(r.alerts.map((a) => a.level)).toEqual(["warning"]);
    r = decide(at(4.5, "warning"), r.memory, t0 + 60_000);
    expect(r.alerts).toEqual([]); // same level within 2 h
    r = decide(at(1.9, "alarm"), r.memory, t0 + 120_000);
    expect(r.alerts.map((a) => a.level)).toEqual(["alarm"]); // a higher level always fires
    r = decide(at(1.8, "alarm"), r.memory, t0 + REPEAT_MS + 120_000);
    expect(r.alerts.map((a) => a.level)).toEqual(["alarm"]); // repeats after 2 h
  });

  it("re-arms after the boat is back in the clear", () => {
    let r = decide(at(4.8, "warning"), {}, t0);
    r = decide(at(8, "clear"), r.memory, t0 + 60_000);
    r = decide(at(4.9, "warning"), r.memory, t0 + 120_000);
    expect(r.alerts.map((a) => a.level)).toEqual(["warning"]);
  });

  it("park alerts are separate from border alerts", () => {
    const r = decide(at(30, "clear", true), {}, t0);
    expect(r.alerts).toEqual([{ rule: "park", level: "inside", imblKm: 30 }]);
  });
});
