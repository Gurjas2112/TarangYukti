import { useTranslation } from "react-i18next";
import { StyleSheet, Text, View } from "react-native";

import type { Brief, Verdict } from "../api/channels";
import { colors, font, radius, space } from "../ui/tokens";

export const verdictColor: Record<Verdict, string> = { GO: colors.go, CAUTION: colors.caution, "NO-GO": colors.noGo };
export const verdictIcon: Record<Verdict, string> = { GO: "✓", CAUTION: "⚠", "NO-GO": "✕" };

/** The verdict in plain words (≥ 40 px), always an icon plus a word, never colour alone (spec §7.1). */
export function VerdictCard({ brief }: { brief: Brief }) {
  const { t } = useTranslation();
  const c = verdictColor[brief.verdict];
  return (
    <View
      style={[styles.card, { borderColor: c }]}
      accessibilityRole="summary"
      accessibilityLiveRegion="polite"
      accessibilityLabel={`${t(`verdict.${brief.verdict}`)}. ${brief.headline}`}
      testID="verdict-card"
    >
      <View style={styles.row}>
        <Text style={[styles.icon, { color: c }]} importantForAccessibility="no">
          {verdictIcon[brief.verdict]}
        </Text>
        <Text style={[styles.verdict, { color: c }]} testID={`verdict-${brief.verdict.toLowerCase()}`}>
          {t(`verdict.${brief.verdict}`)}
        </Text>
      </View>
      <Text style={styles.headline} testID="verdict-headline">
        {brief.headline}
      </Text>
      {brief.window && brief.verdict !== "GO" ? (
        <Text style={styles.body} testID="verdict-window">
          {t("today.window", { depart: brief.window.depart, back: brief.window.back_by })}
        </Text>
      ) : null}
      {brief.simulation ? (
        <Text style={styles.simulation} testID="verdict-simulation">
          {t("today.simulation")}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 3, borderRadius: radius.md, padding: space.md, gap: space.sm, backgroundColor: colors.background },
  row: { flexDirection: "row", alignItems: "center", gap: space.sm },
  icon: { fontSize: font.verdict, fontWeight: "700" },
  verdict: { fontSize: font.verdict, fontWeight: "800" },
  headline: { fontSize: font.title, color: colors.text, fontWeight: "600" },
  body: { fontSize: font.body, color: colors.text },
  simulation: {
    fontSize: font.body,
    color: colors.background,
    backgroundColor: colors.noGo,
    padding: space.xs,
    fontWeight: "700",
  },
});
