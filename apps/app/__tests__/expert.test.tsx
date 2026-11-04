import { describe, expect, it, jest } from "@jest/globals";
import { act, fireEvent, render, screen } from "@testing-library/react-native";
import { createRef } from "react";

import "../src/i18n";

import type { LedgerEntry } from "../src/api/expert";
import { ConstraintLedger } from "../src/components/ConstraintLedger";
import { MissionControl } from "../src/components/MissionControl";
import { handlers, runUiActions } from "../src/copilot/useSeaTools";
import { OceanMap } from "../src/map/OceanMap.native";
import { mapRef } from "../src/map/ref";
import { ALL_LAYERS, type OceanMapHandle, type OceanMapProps, rampColor } from "../src/map/types";

const props: OceanMapProps = {
  initialCenter: { lon: 79.2, lat: 9.25 },
  initialZoom: 8,
  layers: ["land", "imbl"],
  layerBaseUrl: "http://localhost:8002",
  data: { route: { type: "LineString", coordinates: [[79.31, 9.29], [79.3, 9.55]] } },
  testID: "map",
};

describe("OceanMap contract (native implementation)", () => {
  it("honours flyTo, showLayer and drawRoute through the handle", async () => {
    const ref = createRef<OceanMapHandle>();
    await render(<OceanMap ref={ref} {...props} />);
    expect(screen.getByTestId("map-center").props.children.join("")).toContain("9.250, 79.200");
    await act(async () => {
      ref.current!.flyTo(79.313, 9.288, 10);
      ref.current!.showLayer("sst", true);
      ref.current!.showLayer("imbl", false);
      ref.current!.drawRoute(null);
    });
    expect(screen.getByTestId("map-center").props.children.join("")).toContain("9.288, 79.313");
    expect(screen.getByTestId("map-layers").props.children).toBe("land · sst");
  });

  it("lists every layer and colour ramps stay in range", () => {
    expect(ALL_LAYERS).toEqual(expect.arrayContaining(["sst", "chl", "pfz", "imbl", "imblBuffer", "mpa", "route"]));
    for (const v of [-5, 27, 29, 31, 40]) for (const c of rampColor("sst", v)) expect(c).toBeGreaterThanOrEqual(0);
    for (const v of [0, 0.05, 1, 20, 100]) for (const c of rampColor("chl", v)) expect(c).toBeLessThanOrEqual(255);
  });
});

describe("agent UI actions", () => {
  it("fly the shared map and open the ledger; unknown tools are ignored", () => {
    const flyTo = jest.fn();
    mapRef.current = { flyTo, showLayer: jest.fn(), drawRoute: jest.fn(), setTime: jest.fn() };
    const openLedger = jest.fn();
    runUiActions(
      [
        { tool: "flyTo", args: { lat: 9.288, lon: 79.313, zoom: 9 } },
        { tool: "openLedger", args: { answerId: "a1" } },
        { tool: "rm -rf", args: {} },
      ],
      { openLedger },
    );
    expect(flyTo).toHaveBeenCalledWith(79.313, 9.288, 9);
    expect(openLedger).toHaveBeenCalledWith("a1");
    expect(handlers.flyTo({ lat: 9, lon: 79, zoom: 8 })).toBe("ok");
    runUiActions("not a list", {});
    mapRef.current = null;
  });
});

const ledger: LedgerEntry[] = [
  { id: "H1", kind: "hard", name: "Official warning active", ok: true, value: null, unit: null, evidence: [], detail: "", at: null, unknown: false },
  { id: "H2", kind: "hard", name: "IMBL buffer", ok: false, value: 3.2, unit: "km", evidence: ["layer:imbl"], detail: "closest approach", at: null, unknown: false },
  { id: "H8", kind: "hard", name: "Data freshness", ok: false, value: 1, unit: "stale inputs", evidence: ["forecast"], detail: "", at: null, unknown: true },
];

describe("Constraint Ledger", () => {
  it("shows value against limit, marks unknown, and reports the pressed row", async () => {
    const onRow = jest.fn();
    await render(<ConstraintLedger entries={ledger} limits={{ H2: { value: 5, unit: "km", op: ">=" } }} onRow={onRow} />);
    expect(screen.getByText(/3.2 km \(limit >= 5 km\)/)).toBeTruthy();
    expect(screen.getByTestId("ledger-row-H8").props.accessibilityLabel).toContain("unknown");
    fireEvent.press(screen.getByTestId("ledger-row-H2"));
    expect((onRow.mock.calls[0][0] as LedgerEntry).id).toBe("H2");
  });
});

describe("Mission Control", () => {
  it("ticks the agents that ran", async () => {
    await render(<MissionControl steps={["language", "button", "yukti", "explain"]} busy={false} />);
    expect(screen.getByTestId("mission-yukti").props.children.join("")).toContain("✓");
    expect(screen.getByTestId("mission-planner").props.children.join("")).toContain("✓");
    expect(screen.getByTestId("mission-weather").props.children.join("")).toContain("·");
  });
});
