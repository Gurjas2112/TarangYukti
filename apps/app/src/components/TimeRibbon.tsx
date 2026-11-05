import { useTranslation } from "react-i18next";
import { StyleSheet, View } from "react-native";
import { Text } from "../ui/Text";

import type { Brief } from "../api/channels";
import { colors, font, space } from "../ui/tokens";
import { verdictColor, verdictIcon } from "./VerdictCard";

/** Next 24 hours, one bar per hour: the verdict if leaving at that hour. Bar height also encodes the verdict,
 * so it reads without colour. Times stay left-to-right in every language. */
export function TimeRibbon({ ribbon }: { ribbon: Brief["ribbon"] }) {
  const { t } = useTranslation();
  const height = { GO: 36, CAUTION: 22, "NO-GO": 8 } as const;
  const label = ribbon
    .map((r) => `${r.time} ${t(`verdict.${r.verdict}`)}`)
    .filter((_, i) => i % 3 === 0)
    .join(", ");
  return (
    <View accessibilityLabel={`${t("today.next24")}: ${label}`} testID="time-ribbon">
      <Text style={styles.title}>{t("today.next24")}</Text>
      <View style={styles.bars}>
        {ribbon.map((r) => (
          <View key={r.time} style={styles.col}>
            <View style={[styles.bar, { height: height[r.verdict], backgroundColor: verdictColor[r.verdict] }]} />
          </View>
        ))}
      </View>
      <View style={styles.ticks}>
        {ribbon
          .filter((_, i) => i % 6 === 0)
          .map((r) => (
            <Text key={r.time} style={styles.tick}>
              {r.time}
            </Text>
          ))}
      </View>
      <Text style={styles.legend}>
        {(["GO", "CAUTION", "NO-GO"] as const).map((v) => `${verdictIcon[v]} ${t(`verdict.${v}`)}`).join("   ")}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  title: { fontSize: font.body, color: colors.text, fontWeight: "600", marginBottom: space.xs },
  bars: { flexDirection: "row", alignItems: "flex-end", height: 40, gap: 2, direction: "ltr" },
  col: { flex: 1, justifyContent: "flex-end" },
  bar: { borderRadius: 2 },
  ticks: { flexDirection: "row", justifyContent: "space-between", direction: "ltr" },
  tick: { fontSize: font.small, color: colors.textMuted },
  legend: { fontSize: font.small, color: colors.textMuted, marginTop: space.xs },
});
