// The OceanMap contract shared by OceanMap.native.tsx (MapLibre RN) and OceanMap.web.tsx
// (MapLibre GL JS + deck.gl). Implementations arrive in Milestones 7 and 11.

export type LayerId = "sst" | "chl" | "pfz" | "imbl" | "mpa" | "eez" | "route" | "boats" | "warnings";

export interface OceanMapHandle {
  flyTo(lon: number, lat: number, zoom: number): void;
  showLayer(id: LayerId, visible: boolean): void;
  setTime(isoUtc: string): void;
}

export interface OceanMapProps {
  initialCenter: { lon: number; lat: number };
  initialZoom: number;
  layers: LayerId[];
  testID?: string;
}
