// Mission Control (spec §7.10): which agents worked on the last answer — shown behind "Show how it works".
import { useTranslation } from "react-i18next";
import { StyleSheet, Text, View } from "react-native";

import { colors, font, space } from "../ui/tokens";

export const AGENTS = ["language", "planner", "discovery", "weather", "ocean", "knowledge", "geo", "yukti", "explain"] as const;

export function MissionControl({ steps, busy }: { steps: string[]; busy: boolean }) {
  const { t } = useTranslation();
  return (
    <View style={styles.strip} testID="mission-control" accessibilityLabel={t("expert.mission")}>
      <Text style={styles.label}>{t("expert.mission")}:</Text>
      {AGENTS.map((a) => {
        const done = steps.includes(a) || (a === "planner" && steps.includes("button"));
        const icon = done ? "✓" : busy ? "…" : "·";
        return (
          <Text key={a} style={[styles.agent, done && styles.done]} testID={`mission-${a}`}>
            {icon} {t(`agents.${a}`)}
          </Text>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  strip: { flexDirection: "row", flexWrap: "wrap", gap: space.sm, alignItems: "center" },
  label: { fontSize: font.small, fontWeight: "700", color: colors.text },
  agent: { fontSize: 14, color: colors.textMuted },
  done: { color: colors.go, fontWeight: "700" },
});
