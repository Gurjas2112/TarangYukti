// Web map (spec §17.7): MapLibre GL JS for the base (sea, land, border line, marine park) and a deck.gl
// MapboxOverlay for the data layers (SST / chlorophyll points, computed fishing zones, INCOIS points, route,
// the H2 border buffer drawn in metres). No third-party basemap tiles: land comes from our own layer, so the
// map works on any network and shows only official India boundaries we ship (Geospatial Guidelines 2021).
// TODO(tarangyukti): Milestone 11 adds the PMTiles basemap (gom_basemap.pmtiles) via the pmtiles protocol.
import "maplibre-gl/dist/maplibre-gl.css";

import { GeoJsonLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import * as maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";

import { type LayerId, type OceanMapHandle, type OceanMapProps, rampColor } from "./types";

let protocolAdded = false;

const BASE_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "sea", type: "background", paint: { "background-color": "#DCEBF5" } }],
};

type ImblGeo = GeoJSON.FeatureCollection | GeoJSON.Feature;

function linesOf(g: ImblGeo | null): number[][][] {
  if (!g) return [];
  const feats = g.type === "FeatureCollection" ? g.features : [g];
  const out: number[][][] = [];
  for (const f of feats) {
    const geom = f.geometry;
    if (geom.type === "LineString") out.push(geom.coordinates as number[][]);
    if (geom.type === "MultiLineString") out.push(...(geom.coordinates as number[][][]));
  }
  return out;
}

export const OceanMap = forwardRef<OceanMapHandle, OceanMapProps>(function OceanMap(
  { initialCenter, initialZoom, layers, data, layerBaseUrl, onLayersChange, testID },
  ref,
) {
  const el = useRef<HTMLDivElement | null>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const [visible, setVisible] = useState<Set<LayerId>>(new Set(layers));
  const [route, setRoute] = useState<GeoJSON.LineString | null>(data?.route ?? null);
  const [imbl, setImbl] = useState<ImblGeo | null>(null);
  const [land, setLand] = useState<GeoJSON.GeoJSON | null>(null);
  const [mpa, setMpa] = useState<GeoJSON.GeoJSON | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => setRoute(data?.route ?? null), [data?.route]);
  useEffect(() => setVisible(new Set(layers)), [layers]);

  useImperativeHandle(
    ref,
    () => ({
      flyTo: (lon, lat, zoom) => map.current?.flyTo({ center: [lon, lat], zoom, essential: true }),
      showLayer: (id, on) =>
        setVisible((v) => {
          const n = new Set(v);
          if (on) n.add(id);
          else n.delete(id);
          onLayersChange?.([...n]);
          return n;
        }),
      drawRoute: (r) => setRoute(r),
      setTime: () => {
        // hourly layers (forecast) follow the departure slider through the plan; static here
      },
    }),
    [onLayersChange],
  );

  // map + base layers, once
  useEffect(() => {
    if (!el.current) return;
    if (!protocolAdded) {
      maplibregl.addProtocol("pmtiles", new Protocol().tile);
      protocolAdded = true;
    }
    const m = new maplibregl.Map({
      container: el.current,
      style: BASE_STYLE,
      center: [initialCenter.lon, initialCenter.lat],
      zoom: initialZoom,
      attributionControl: { compact: true, customAttribution: "Border line: India–Sri Lanka 1974/1976 agreements; park: WDPA" },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    m.on("load", async () => {
      const [land, line, mpa] = await Promise.all(
        ["land", "imbl", "mpa"].map((n) => fetch(`${layerBaseUrl}/layers/${n}`).then((r) => r.json())),
      );
      setLand(land);
      setMpa(mpa);
      setImbl(line as ImblGeo);
      // overlay mode: everything we draw is a deck.gl layer, in one explicit order (data under land and lines)
      overlay.current = new MapboxOverlay({ interleaved: false, layers: [] });
      m.addControl(overlay.current as unknown as maplibregl.IControl);
      setReady(true);
    });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // data layers (deck.gl)
  useEffect(() => {
    if (!ready || !overlay.current) return;
    const bufferKm = data?.imblBufferKm ?? 0;
    overlay.current.setProps({
      layers: [
        visible.has("sst") &&
          new ScatterplotLayer({
            id: "sst",
            data: data?.sst ?? [],
            getPosition: (p: { lon: number; lat: number }) => [p.lon, p.lat],
            getFillColor: (p: { value: number }) => rampColor("sst", p.value),
            getRadius: 13000,
            radiusUnits: "meters",
            pickable: true,
          }),
        visible.has("chl") &&
          new ScatterplotLayer({
            id: "chl",
            data: data?.chl ?? [],
            getPosition: (p: { lon: number; lat: number }) => [p.lon, p.lat],
            getFillColor: (p: { value: number }) => rampColor("chl", p.value),
            getRadius: 2300,
            radiusUnits: "meters",
          }),
        visible.has("land") &&
          land &&
          new GeoJsonLayer({
            id: "land",
            data: land,
            getFillColor: [239, 233, 220, 255],
            getLineColor: [156, 145, 128, 255],
            lineWidthMinPixels: 1,
          }),
        visible.has("mpa") &&
          mpa &&
          new GeoJsonLayer({
            id: "mpa",
            data: mpa,
            getFillColor: [46, 139, 87, 50],
            getLineColor: [31, 107, 66, 255],
            lineWidthMinPixels: 1.5,
          }),
        visible.has("imblBuffer") &&
          bufferKm > 0 &&
          new PathLayer({
            id: "imbl-buffer",
            data: linesOf(imbl),
            getPath: (d: number[][]) => d as [number, number][],
            getColor: [192, 57, 43, 70],
            getWidth: bufferKm * 2000, // the buffer on both sides of the line
            widthUnits: "meters",
            capRounded: true,
          }),
        visible.has("imbl") &&
          new PathLayer({
            id: "imbl",
            data: linesOf(imbl),
            getPath: (d: number[][]) => d as [number, number][],
            getColor: [192, 57, 43, 255],
            getWidth: 3,
            widthUnits: "pixels",
          }),
        visible.has("pfz") &&
          new GeoJsonLayer({
            id: "pfz",
            data: {
              type: "FeatureCollection",
              features: (data?.pfz ?? []).map((z) => ({ type: "Feature", properties: { id: z.id }, geometry: z.geometry })),
            } as GeoJSON.FeatureCollection,
            getFillColor: [242, 107, 33, 60],
            getLineColor: [242, 107, 33, 230],
            lineWidthMinPixels: 2,
          }),
        visible.has("incois") &&
          new ScatterplotLayer({
            id: "incois",
            data: data?.incois ?? [],
            getPosition: (p: { lon: number; lat: number }) => [p.lon, p.lat],
            getFillColor: [242, 107, 33, 255],
            getLineColor: [0, 0, 0, 255],
            stroked: true,
            getRadius: 6,
            radiusUnits: "pixels",
          }),
        visible.has("route") &&
          route &&
          new PathLayer({
            id: "route",
            data: [route.coordinates],
            getPath: (d: number[][]) => d as [number, number][],
            getColor: [47, 111, 222, 255],
            getWidth: 4,
            widthUnits: "pixels",
          }),
        data?.harbour &&
          new ScatterplotLayer({
            id: "harbour",
            data: [data.harbour],
            getPosition: (h: { lon: number; lat: number }) => [h.lon, h.lat],
            getFillColor: [11, 29, 46, 255],
            getRadius: 7,
            radiusUnits: "pixels",
          }),
      ].filter(Boolean),
    });
  }, [data, visible, route, imbl, land, mpa, ready]);

  return <div ref={el} data-testid={testID} style={{ position: "absolute", inset: 0 }} />;
});
