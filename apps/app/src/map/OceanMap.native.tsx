// Android map. MapLibre React Native with local PMTiles arrives in Milestone 11 (offline trip maps); until then
// this honours the same contract and lists what the map would show, so screens and the agent's frontend tools
// work unchanged on both targets.
import { forwardRef, useImperativeHandle, useState } from "react";
import { StyleSheet, View } from "react-native";
import { Text } from "../ui/Text";

import { colors, font, space } from "../ui/tokens";
import type { LayerId, OceanMapHandle, OceanMapProps } from "./types";

export const OceanMap = forwardRef<OceanMapHandle, OceanMapProps>(function OceanMap(
  { initialCenter, initialZoom, layers, data, testID },
  ref,
) {
  const [center, setCenter] = useState({ ...initialCenter, zoom: initialZoom });
  const [visible, setVisible] = useState<LayerId[]>(layers);
  const [route, setRoute] = useState(data?.route ?? null);
  useImperativeHandle(ref, () => ({
    flyTo: (lon, lat, zoom) => setCenter({ lon, lat, zoom }),
    showLayer: (id, on) => setVisible((v) => (on ? [...new Set([...v, id])] : v.filter((x) => x !== id))),
    drawRoute: (r) => setRoute(r),
    setTime: () => undefined,
  }));
  return (
    <View style={styles.box} testID={testID} accessibilityLabel="map">
      <Text style={styles.text} testID="map-center">
        {center.lat.toFixed(3)}, {center.lon.toFixed(3)} · z{center.zoom}
      </Text>
      <Text style={styles.text} testID="map-layers">
        {visible.join(" · ")}
      </Text>
      {route ? <Text style={styles.text}>route: {route.coordinates.length} points</Text> : null}
    </View>
  );
});

const styles = StyleSheet.create({
  box: { flex: 1, backgroundColor: "#DCEBF5", padding: space.md, gap: space.xs },
  text: { fontSize: font.small, color: colors.text },
});
