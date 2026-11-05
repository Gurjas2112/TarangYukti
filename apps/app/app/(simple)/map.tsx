// Map tab. The OceanMap (MapLibre, offline PMTiles) arrives in Milestones 7 and 11; until then the tab shows the
// same facts in words: fishing spot and border line from today's card.
import { useTranslation } from "react-i18next";
import { ScrollView, StyleSheet } from "react-native";
import { Text } from "../../src/ui/Text";

import { useBrief } from "../../src/brief/useBrief";
import { usePrefs } from "../../src/state/prefs";
import { colors, font, space } from "../../src/ui/tokens";

export default function MapTab() {
  const { t } = useTranslation();
  const { prefs, lang } = usePrefs();
  const { brief } = useBrief(prefs.harbour, prefs.boatKind, lang);
  return (
    <ScrollView contentContainerStyle={styles.root} testID="map-screen">
      <Text style={styles.body}>{t("map.soon")}</Text>
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
  root: { padding: space.lg, gap: space.md, backgroundColor: colors.background, flexGrow: 1 },
  body: { fontSize: font.body, color: colors.text },
  line: { fontSize: font.body + 2, color: colors.text, fontWeight: "600" },
  footer: { fontSize: font.small, color: colors.textMuted },
});
