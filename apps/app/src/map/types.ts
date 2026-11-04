// The OceanMap contract (spec §17.7) shared by OceanMap.web.tsx (MapLibre GL JS + deck.gl, Milestone 7) and
// OceanMap.native.tsx (MapLibre React Native with offline PMTiles, Milestone 11). Screens import "./OceanMap"
// and never know which one they got.

export type LayerId =
  | "sst"
  | "chl"
  | "pfz"
  | "incois"
  | "imbl"
  | "imblBuffer"
  | "mpa"
  | "land"
  | "route"
  | "boats"
  | "warnings";

export type GridPoint = { lat: number; lon: number; value: number };

export type PfzZone = {
  id: string;
  centroid: { lat: number; lon: number };
  area_km2: number;
  mean_chl_mg_m3: number;
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon;
};

/** Live data the map draws; the static layers (land, border line, marine park) it fetches itself. */
export interface OceanMapData {
  sst?: GridPoint[];
  chl?: GridPoint[];
  pfz?: PfzZone[];
  incois?: { lat: number; lon: number }[];
  route?: GeoJSON.LineString | null;
  harbour?: { lat: number; lon: number; name: string };
  /** Width of the border buffer drawn for H2, in km (from the ledger, not hard-coded). */
  imblBufferKm?: number;
}

export interface OceanMapHandle {
  flyTo(lon: number, lat: number, zoom: number): void;
  showLayer(id: LayerId, visible: boolean): void;
  drawRoute(route: GeoJSON.LineString | null): void;
  /** The time the map is showing (ISO, UTC); layers that change by hour follow it. */
  setTime(isoUtc: string): void;
}

export interface OceanMapProps {
  initialCenter: { lon: number; lat: number };
  initialZoom: number;
  layers: LayerId[];
  data?: OceanMapData;
  layerBaseUrl: string;
  onLayersChange?: (layers: LayerId[]) => void;
  testID?: string;
}

export const ALL_LAYERS: LayerId[] = ["land", "sst", "chl", "pfz", "incois", "imbl", "imblBuffer", "mpa", "route"];

/** Blue → red SST ramp, light → dark green chlorophyll ramp (values outside the range are clamped). */
export function rampColor(kind: "sst" | "chl", v: number): [number, number, number, number] {
  if (kind === "sst") {
    const t = Math.min(1, Math.max(0, (v - 27) / 4)); // 27–31 °C
    return [Math.round(40 + 215 * t), Math.round(90 + 40 * (1 - Math.abs(t - 0.5) * 2)), Math.round(220 - 200 * t), 95];
  }
  const t = Math.min(1, Math.max(0, Math.log10(Math.max(v, 0.05)) / Math.log10(20) + 0.35)); // ~0.05–20 mg/m³, log
  return [Math.round(200 - 180 * t), Math.round(230 - 110 * t), Math.round(150 - 130 * t), 120];
}
