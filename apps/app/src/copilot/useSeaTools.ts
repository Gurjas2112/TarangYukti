// CopilotKit frontend tools (spec §17.8): the agent drives the map and opens the ledger and citations.
// flyTo and openWhy work on both targets; showLayer, drawRoute, setTime, openLedger and openCitation are
// registered only on Expert routes. The agent's final state also lists `ui_actions` (deterministic, from the
// Yukti result) which the app runs through these same handlers after each answer.
import { useFrontendTool } from "@copilotkit/react-native/headless";
import { z } from "zod";

import { mapRef } from "../map/ref";
import type { LayerId } from "../map/types";

export type SeaHandlers = {
  openWhy?: (answerId: string) => void;
  openLedger?: (answerId: string) => void;
  openCitation?: (chunkId: number) => void;
  setDepart?: (isoUtc: string) => void;
};

const LAYERS = ["sst", "chl", "pfz", "incois", "imbl", "imblBuffer", "mpa", "land", "route"] as const;

export const handlers = {
  flyTo: (a: { lat: number; lon: number; zoom: number }) => {
    mapRef.current?.flyTo(a.lon, a.lat, a.zoom);
    return "ok";
  },
};

/** Run the agent's `ui_actions` with the registered handlers (unknown tools are ignored). */
export function runUiActions(actions: unknown, h: SeaHandlers): void {
  if (!Array.isArray(actions)) return;
  for (const a of actions) {
    const tool = (a as { tool?: string }).tool;
    const args = (a as { args?: Record<string, unknown> }).args ?? {};
    if (tool === "flyTo") handlers.flyTo(args as { lat: number; lon: number; zoom: number });
    else if (tool === "openLedger" && typeof args.answerId === "string") h.openLedger?.(args.answerId);
    else if (tool === "openWhy" && typeof args.answerId === "string") h.openWhy?.(args.answerId);
  }
}

/** flyTo and openWhy, on both targets. */
export function useSeaTools(h: SeaHandlers) {
  useFrontendTool({
    name: "flyTo",
    description: "Move the map to a place before showing results there. lat 8.0–10.5, lon 78.0–80.5.",
    parameters: z.object({ lat: z.number().min(8).max(10.5), lon: z.number().min(78).max(80.5), zoom: z.number().min(5).max(14) }),
    handler: async (a) => handlers.flyTo(a),
  });
  useFrontendTool({
    name: "openWhy",
    description: "Open the one-sentence reason for the current verdict.",
    parameters: z.object({ answerId: z.string() }),
    handler: async ({ answerId }) => {
      h.openWhy?.(answerId);
      return "opened";
    },
  });
}

/** Expert-only tools: call this hook only on Expert routes. */
export function useExpertTools(h: SeaHandlers) {
  useFrontendTool({
    name: "showLayer",
    description: "Show or hide a map layer (Expert mode).",
    parameters: z.object({ layer: z.enum(LAYERS), visible: z.boolean() }),
    handler: async ({ layer, visible }) => {
      mapRef.current?.showLayer(layer as LayerId, visible);
      return "ok";
    },
  });
  useFrontendTool({
    name: "drawRoute",
    description: "Draw a route on the map as a list of [lon, lat] points (Expert mode).",
    parameters: z.object({ coordinates: z.array(z.tuple([z.number(), z.number()])).min(2) }),
    handler: async ({ coordinates }) => {
      mapRef.current?.drawRoute({ type: "LineString", coordinates });
      return "ok";
    },
  });
  useFrontendTool({
    name: "setTime",
    description: "Set the departure time the console evaluates (ISO 8601 with timezone, within the next 24 h).",
    parameters: z.object({ iso: z.string() }),
    handler: async ({ iso }) => {
      h.setDepart?.(iso);
      mapRef.current?.setTime(iso);
      return "ok";
    },
  });
  useFrontendTool({
    name: "openLedger",
    description: "Open the full Constraint Ledger for an answer (Expert mode only).",
    parameters: z.object({ answerId: z.string() }),
    handler: async ({ answerId }) => {
      h.openLedger?.(answerId);
      return "opened";
    },
  });
  useFrontendTool({
    name: "openCitation",
    description: "Open the source passage of a citation (Expert mode).",
    parameters: z.object({ chunkId: z.number().int() }),
    handler: async ({ chunkId }) => {
      h.openCitation?.(chunkId);
      return "opened";
    },
  });
}
