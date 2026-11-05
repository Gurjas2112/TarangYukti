// Android map (spec §17.6–17.7): MapLibre React Native drawing only bundled and passed-in GeoJSON, so the trip
// map works with no network at all — coastline, border line, marine park, fishing zones, route, harbour and the
// boat's own position. Same OceanMap contract as the web build, so screens and frontend tools are unchanged.
// TODO(tarangyukti): a detailed street/label basemap from an offline PMTiles extract (pmtiles CLI not yet approved
//   on the build laptop); the coastline layer stands in for it and is accurate enough for border and park safety.
import { Camera, type CameraRef, GeoJSONSource, Layer, Map, UserLocation } from "@maplibre/maplibre-react-native";
import { forwardRef, useImperativeHandle, useMemo, useRef, useState } from "react";
import { StyleSheet, View } from "react-native";

import imbl from "../safety/layers/imbl.json";
import land from "../safety/layers/land.json";
import mpa from "../safety/layers/mpa.json";
import type { LayerId, OceanMapHandle, OceanMapProps } from "./types";

// No tiles, no glyphs, no sprites: a sea-coloured background that never needs the network.
const STYLE = {
  version: 8 as const,
  sources: {},
  layers: [{ id: "sea", type: "background" as const, paint: { "background-color": "#BFDDF0" } }],
};

const fc = (features: GeoJSON.Feature[]): GeoJSON.FeatureCollection => ({ type: "FeatureCollection", features });

export const OceanMap = forwardRef<OceanMapHandle, OceanMapProps>(function OceanMap(
  { initialCenter, initialZoom, layers, data, testID },
  ref,
) {
  const camera = useRef<CameraRef>(null);
  const [visible, setVisible] = useState<LayerId[]>(layers);
  const [route, setRoute] = useState<GeoJSON.LineString | null>(data?.route ?? null);
  useImperativeHandle(ref, () => ({
    flyTo: (lon, lat, zoom) => camera.current?.flyTo({ center: [lon, lat], zoom, duration: 1500 }),
    showLayer: (id, on) => setVisible((v) => (on ? [...new Set([...v, id])] : v.filter((x) => x !== id))),
    drawRoute: (r) => {
      setRoute(r);
      if (r) setVisible((v) => [...new Set([...v, "route" as LayerId])]); // a route the agent draws is shown
    },
    setTime: () => undefined,
  }));
  const show = (id: LayerId) => visible.includes(id);

  const pfz = useMemo(
    () => fc((data?.pfz ?? []).map((z) => ({ type: "Feature", properties: { id: z.id }, geometry: z.geometry }))),
    [data?.pfz],
  );
  const incois = useMemo(
    () =>
      fc(
        (data?.incois ?? []).map((p) => ({
          type: "Feature",
          properties: {},
          geometry: { type: "Point", coordinates: [p.lon, p.lat] },
        })),
      ),
    [data?.incois],
  );
  const harbour = data?.harbour;

  return (
    <View style={styles.box} testID={testID} accessibilityLabel="map">
      <Map style={styles.map} mapStyle={STYLE} attribution={false} logo={false} compass>
        <Camera
          ref={camera}
          initialViewState={{ center: [initialCenter.lon, initialCenter.lat], zoom: initialZoom }}
          minZoom={6}
          maxZoom={14}
        />
        <GeoJSONSource id="land" data={land as unknown as GeoJSON.FeatureCollection}>
          <Layer id="land-fill" type="fill" paint={{ "fill-color": "#F4F1E8", "fill-outline-color": "#7A7A7A" }} />
        </GeoJSONSource>
        {show("mpa") ? (
          <GeoJSONSource id="mpa" data={mpa as unknown as GeoJSON.FeatureCollection}>
            <Layer id="mpa-fill" type="fill" paint={{ "fill-color": "#2E8B57", "fill-opacity": 0.25 }} />
            <Layer id="mpa-line" type="line" paint={{ "line-color": "#1F6B42", "line-width": 1.5 }} />
          </GeoJSONSource>
        ) : null}
        {show("pfz") && pfz.features.length ? (
          <GeoJSONSource id="pfz" data={pfz}>
            <Layer id="pfz-fill" type="fill" paint={{ "fill-color": "#F26B21", "fill-opacity": 0.45 }} />
          </GeoJSONSource>
        ) : null}
        {show("incois") && incois.features.length ? (
          <GeoJSONSource id="incois" data={incois}>
            <Layer id="incois-dot" type="circle" paint={{ "circle-radius": 5, "circle-color": "#7A3E00" }} />
          </GeoJSONSource>
        ) : null}
        {show("imbl") ? (
          <GeoJSONSource id="imbl" data={imbl as unknown as GeoJSON.FeatureCollection}>
            <Layer
              id="imbl-line"
              type="line"
              paint={{ "line-color": "#A30000", "line-width": 3, "line-dasharray": [2, 1.5] }}
            />
          </GeoJSONSource>
        ) : null}
        {show("route") && route ? (
          <GeoJSONSource id="route" data={{ type: "Feature", properties: {}, geometry: route }}>
            <Layer id="route-line" type="line" paint={{ "line-color": "#0040A0", "line-width": 4 }} />
          </GeoJSONSource>
        ) : null}
        {harbour ? (
          <GeoJSONSource
            id="harbour"
            data={{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [harbour.lon, harbour.lat] } }}
          >
            <Layer
              id="harbour-dot"
              type="circle"
              paint={{ "circle-radius": 7, "circle-color": "#000000", "circle-stroke-color": "#FFFFFF", "circle-stroke-width": 2 }}
            />
          </GeoJSONSource>
        ) : null}
        <UserLocation accuracy heading />
      </Map>
    </View>
  );
});

const styles = StyleSheet.create({
  box: { flex: 1, minHeight: 320 },
  map: { flex: 1 },
});
