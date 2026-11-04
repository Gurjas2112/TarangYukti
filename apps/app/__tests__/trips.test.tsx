import { describe, expect, it } from "@jest/globals";

import { catalogues } from "../src/i18n/catalogues";
import { inRegion } from "../src/location/useLiveTracking";

describe("live tracking", () => {
  it("sends positions only inside the prototype region", () => {
    expect(inRegion(9.288, 79.313)).toBe(true);
    expect(inRegion(13.08, 80.27)).toBe(false); // Chennai
    expect(inRegion(9.3, 81.0)).toBe(false); // east of the region
  });
});

describe("trip and family strings", () => {
  it("every catalogue has the trip and family keys with their variables", () => {
    for (const [code, cat] of Object.entries(catalogues)) {
      expect([code, cat["trip.rightOn"]?.includes("{{right}}")]).toEqual([code, true]);
      expect([code, cat["family.backAt"]?.includes("{{time}}")]).toEqual([code, true]);
    }
  });
});
