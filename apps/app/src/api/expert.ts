// Expert console and analyst data from ty-channels (public, no personal data). Zod-checked.
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { getEnv } from "../env";
import type { BoatKind } from "./channels";

export const LedgerEntrySchema = z.object({
  id: z.string(),
  kind: z.enum(["hard", "soft"]),
  name: z.string(),
  ok: z.boolean(),
  value: z.union([z.number(), z.string(), z.null()]),
  unit: z.string().nullable(),
  evidence: z.array(z.string()),
  detail: z.string(),
  at: z.string().nullable(),
  unknown: z.boolean(),
});
export type LedgerEntry = z.infer<typeof LedgerEntrySchema>;

const EvalSchema = z.object({
  outcome: z.enum(["GO", "CAUTION", "NO-GO"]),
  feasible: z.boolean(),
  failed_hard: z.array(z.string()),
  risk: z.number().nullable(),
  depart: z.string(),
  return_at: z.string(),
  route_km: z.number(),
  ledger: z.array(LedgerEntrySchema),
  route: z.any().nullable().optional(),
});
export type Evaluation = z.infer<typeof EvalSchema>;

export const PlanSchema = z.object({
  source: z.string(),
  fetched_at: z.string(),
  confidence: z.string(),
  cache: z.string(),
  notes: z.array(z.string()),
  data: z.object({
    verdict: z.enum(["GO", "CAUTION", "NO-GO"]),
    boat_type: z.string(),
    as_of: z.string(),
    requested: EvalSchema,
    earliest_window: EvalSchema.nullable(),
    recommended: EvalSchema.nullable(),
    checked_departures: z.number(),
    answer_id: z.string().nullable(),
    harbour: z.object({ id: z.string(), name: z.string(), lat: z.number(), lon: z.number() }),
    limits: z.record(z.string(), z.object({ value: z.number(), unit: z.string(), op: z.string() })),
  }),
});
export type Limits = Plan["data"]["limits"];
export type Plan = z.infer<typeof PlanSchema>;

const PointSchema = z.object({ lat: z.number(), lon: z.number(), value: z.number() });
const GridSchema = z.object({
  source: z.string(),
  data: z.object({
    available: z.boolean().optional(),
    reason: z.string().optional(),
    time: z.string().optional(),
    unit: z.string().optional(),
    age_hours: z.number().nullable().optional(),
    stats: z.object({ min: z.number(), max: z.number(), mean: z.number(), masked_fraction: z.number() }).optional(),
    points: z.array(PointSchema).optional(),
  }),
  notes: z.array(z.string()),
});
export type Grid = z.infer<typeof GridSchema>;

const PfzSchema = z.object({
  computed: z.object({
    source: z.string(),
    notes: z.array(z.string()),
    data: z.object({
      available: z.boolean().optional(),
      reason: z.string().optional(),
      zones: z.array(z.any()).optional(),
      overlap_incois: z.number().nullable().optional(),
      incois_points: z.number().optional(),
      front_cells: z.number().optional(),
    }),
  }),
  incois: z.object({
    data: z.object({ available: z.boolean().optional(), zones: z.array(z.object({ lat: z.number(), lon: z.number() })).optional() }),
  }),
});
export type Pfz = z.infer<typeof PfzSchema>;

const AnomalySchema = z.object({
  source: z.string(),
  data: z.object({
    available: z.boolean().optional(),
    reason: z.string().optional(),
    point: z.object({ lat: z.number(), lon: z.number() }).optional(),
    series: z.array(z.object({ date: z.string(), sst_c: z.number().nullable(), anom_c: z.number().nullable() })).optional(),
    heatwave: z
      .object({ tested: z.boolean(), heatwave: z.boolean().optional(), mean_anom_c: z.number().optional(), threshold_c: z.number().optional() })
      .optional(),
  }),
});
export type Anomaly = z.infer<typeof AnomalySchema>;

export const ChunkSchema = z.object({
  id: z.number(),
  content: z.string(),
  heading_path: z.string().nullable().optional(),
  issuer: z.string(),
  source_id: z.string(),
  version: z.union([z.string(), z.number()]).nullable(),
  url: z.string().nullable(),
  valid_from: z.string().nullable(),
  valid_to: z.string().nullable(),
  status: z.string(),
  language: z.string().nullable(),
});
export type Chunk = z.infer<typeof ChunkSchema>;

const DocsSchema = z.object({
  documents: z.array(
    z.object({
      id: z.string(),
      source_id: z.string(),
      issuer: z.string(),
      doc_type: z.string().nullable(),
      language: z.string().nullable(),
      url: z.string().nullable(),
      status: z.string(),
      valid_to: z.string().nullable(),
      chunks: z.number(),
    }),
  ),
});

export const base = () => getEnv().CHANNELS_URL;

async function get<T>(path: string, schema: z.ZodType<T>): Promise<T> {
  const r = await fetch(`${base()}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return schema.parse(await r.json());
}

export const expertApi = {
  plan: (harbour: string, boat: BoatKind, departAt?: string | null, goal?: { lat: number; lon: number } | null) => {
    const q = new URLSearchParams({ harbour, boat_type: boat });
    if (departAt) q.set("depart_at", departAt);
    if (goal) {
      q.set("goal_lat", String(goal.lat));
      q.set("goal_lon", String(goal.lon));
    }
    return get(`/expert/plan?${q}`, PlanSchema);
  },
  grid: (kind: "sst" | "chl") => get(`/grids/${kind}`, GridSchema),
  pfz: () => get("/pfz", PfzSchema),
  anomaly: (lat: number, lon: number) => get(`/anomaly?lat=${lat}&lon=${lon}&days=30`, AnomalySchema),
  chunk: (id: number) => get(`/sources/chunk/${id}`, ChunkSchema),
  documents: () => get("/kb/documents", DocsSchema).then((d) => d.documents),
  netcdf: (kind: "sst" | "chl") => get(`/grids/${kind}/netcdf`, z.object({ url: z.string(), source: z.string() })),
  csvUrl: (kind: "sst" | "chl") => `${base()}/grids/${kind}/csv`,
};

export function usePlan(harbour: string, boat: BoatKind, departAt: string | null) {
  return useQuery({
    queryKey: ["plan", harbour, boat, departAt],
    queryFn: () => expertApi.plan(harbour, boat, departAt),
    enabled: Boolean(harbour),
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });
}

export const useGrid = (kind: "sst" | "chl", enabled = true) =>
  useQuery({ queryKey: ["grid", kind], queryFn: () => expertApi.grid(kind), staleTime: 600_000, enabled });
export const usePfz = (enabled = true) =>
  useQuery({ queryKey: ["pfz"], queryFn: expertApi.pfz, staleTime: 600_000, enabled });
export const useAnomaly = (lat: number, lon: number, enabled = true) =>
  useQuery({ queryKey: ["anomaly", lat, lon], queryFn: () => expertApi.anomaly(lat, lon), staleTime: 3_600_000, enabled });
