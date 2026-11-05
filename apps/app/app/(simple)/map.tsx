// Map tab (spec §17.6): the coastline, border line, marine park, home harbour and your position — on Android
// drawn entirely from data bundled in the app, so it works at sea with no signal. Below the map the same facts
// in words: the nearest fishing spot and the border distance from today's card.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ScrollView, StyleSheet, View } from "react-native";

import { api } from "../../src/api/channels";
import { useBrief } from "../../src/brief/useBrief";
import { getEnv } from "../../src/env";
import { OceanMap } from "../../src/map/OceanMap";
import { usePrefs } from "../../src/state/prefs";
import { Text } from "../../src/ui/Text";
import { colors, font, space } from "../../src/ui/tokens";

const RAMESWARAM = { lat: 9.288, lon: 79.313 }; // region centre fallback until the harbour list loads

export default function MapTab() {
  const { t } = useTranslation();
  const { prefs, lang } = usePrefs();
  const { brief } = useBrief(prefs.harbour, prefs.boatKind, lang);
  const harbours = useQuery({ queryKey: ["harbours"], queryFn: api.harbours, staleTime: 24 * 3600_000 });
  const home = harbours.data?.find((h) => h.id === prefs.harbour);
  const centre = home ? { lat: home.lat, lon: home.lon } : RAMESWARAM;
  return (
    <ScrollView contentContainerStyle={styles.root} testID="map-screen">
      <View style={styles.map}>
        <OceanMap
          key={home?.id ?? "region"}
          initialCenter={centre}
          initialZoom={9}
          layers={["land", "imbl", "mpa", "route"]}
          data={home ? { harbour: { lat: home.lat, lon: home.lon, name: home.name } } : undefined}
          layerBaseUrl={getEnv().CHANNELS_URL}
          testID="ocean-map"
        />
      </View>
      <Text style={styles.legend}>{t("map.legend")}</Text>
      {brief?.spot ? (
        <Text style={styles.line} testID="map-spot">
          🐟 {brief.spot.text}
        </Text>
      ) : null}
      {brief ? (
        <Text style={styles.line} testID="map-border">
          🚩 {brief.border.text}
        </Text>
      ) : null}
      {brief ? <Text style={styles.footer}>{brief.footer}</Text> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { padding: space.md, gap: space.md, backgroundColor: colors.background, flexGrow: 1 },
  map: { height: 380, borderRadius: 8, overflow: "hidden", borderWidth: 1, borderColor: colors.border },
  legend: { fontSize: font.small, color: colors.textMuted },
  line: { fontSize: font.body + 2, color: colors.text, fontWeight: "600" },
  footer: { fontSize: font.small, color: colors.textMuted },
});
