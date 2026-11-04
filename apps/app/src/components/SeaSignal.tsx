// Sea Signal (spec §7.5): the Expert verdict with its earliest and recommended windows and data freshness.
import { useTranslation } from "react-i18next";
import { StyleSheet, Text, View } from "react-native";

import type { Plan } from "../api/expert";
import { colors, font, radius, space } from "../ui/tokens";
import { verdictColor, verdictIcon } from "./VerdictCard";

const hhmm = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

export function SeaSignal({ plan }: { plan: Plan }) {
  const { t } = useTranslation();
  const d = plan.data;
  const c = verdictColor[d.verdict];
  const failed = d.requested.failed_hard;
  const notes = plan.notes.filter((n) => !n.startsWith("as of"));
  return (
    <View style={[styles.card, { borderColor: c }]} testID="sea-signal" accessibilityLiveRegion="polite">
      <Text style={[styles.verdict, { color: c }]} testID={`sea-signal-${d.verdict.toLowerCase()}`}>
        {verdictIcon[d.verdict]} {d.verdict}
        {d.verdict === "GO" ? <Text style={styles.small}> — {t("expert.advisoryOnly")}</Text> : null}
      </Text>
      <Text style={styles.line}>
        {t("expert.depart")} {hhmm(d.requested.depart)} → {t("expert.back")} {hhmm(d.requested.return_at)} IST
        {d.requested.risk !== null ? ` · ${t("expert.risk")} ${d.requested.risk.toFixed(2)}` : ""}
      </Text>
      {failed.length ? <Text style={styles.line}>{t("expert.failed")}: {failed.join(", ")}</Text> : null}
      {d.earliest_window ? (
        <Text style={styles.line} testID="earliest-window">
          {t("expert.earliest")}: {hhmm(d.earliest_window.depart)} ({d.earliest_window.outcome})
        </Text>
      ) : (
        <Text style={styles.line} testID="earliest-window">
          {t("expert.noWindow")}
        </Text>
      )}
      {d.recommended ? (
        <Text style={styles.line}>
          {t("expert.recommended")}: {hhmm(d.recommended.depart)} ({d.recommended.outcome})
        </Text>
      ) : null}
      <Text style={styles.meta}>
        {t("expert.asOf")} {hhmm(d.as_of)} IST · {plan.confidence} · {plan.cache}
        {notes.length ? ` · ${notes.join(" · ")}` : ""}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderWidth: 3, borderRadius: radius.md, padding: space.md, gap: space.xs, backgroundColor: colors.background },
  verdict: { fontSize: font.title, fontWeight: "800" },
  small: { fontSize: font.small, fontWeight: "600", color: colors.textMuted },
  line: { fontSize: font.small, color: colors.text },
  meta: { fontSize: 13, color: colors.textMuted },
});
