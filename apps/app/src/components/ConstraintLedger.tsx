// The Constraint Ledger (spec §7.5): every rule, its value, limit/evidence and source — open by default in Expert
// mode. Tapping a failed H2 row draws the border buffer on the map.
import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { LedgerEntry, Limits } from "../api/expert";
import { colors, font, space } from "../ui/tokens";

const IST = { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false } as const;

function status(e: LedgerEntry): { icon: string; color: string; label: string } {
  if (e.unknown) return { icon: "?", color: colors.caution, label: "unknown" };
  if (e.ok) return { icon: "✓", color: colors.go, label: "pass" };
  return e.kind === "hard"
    ? { icon: "✕", color: colors.noGo, label: "fail" }
    : { icon: "!", color: colors.caution, label: "warn" };
}

type Props = { entries: LedgerEntry[]; limits?: Limits; onRow?: (e: LedgerEntry) => void };

export function ConstraintLedger({ entries, limits, onRow }: Props) {
  const { t } = useTranslation();
  return (
    <View style={styles.table} testID="ledger" accessibilityRole="list">
      <Text style={styles.title} accessibilityRole="header">
        {t("expert.ledger")}
      </Text>
      {entries.map((e) => {
        const s = status(e);
        const lim = limits?.[e.id];
        const shown = e.value === null || e.value === undefined ? "—" : `${e.value}${e.unit ? ` ${e.unit}` : ""}`;
        const value = lim ? `${shown} (${t("expert.limit")} ${lim.op} ${lim.value} ${lim.unit})` : shown;
        return (
          <Pressable
            key={e.id}
            onPress={() => onRow?.(e)}
            style={({ pressed }) => [styles.row, pressed && styles.pressed]}
            accessibilityRole="button"
            accessibilityLabel={`${e.id} ${e.name}: ${s.label}. ${e.detail}`}
            testID={`ledger-row-${e.id}`}
          >
            <Text style={[styles.status, { color: s.color }]}>{s.icon}</Text>
            <Text style={styles.id}>{e.id}</Text>
            <View style={styles.body}>
              <Text style={styles.name}>
                {e.name} <Text style={styles.value}>· {value}</Text>
              </Text>
              {e.detail ? <Text style={styles.detail}>{e.detail}</Text> : null}
              {e.at ? (
                <Text style={styles.meta}>
                  {t("expert.at")} {new Date(e.at).toLocaleTimeString("en-IN", IST)} IST
                  {e.evidence.length ? ` · ${e.evidence.join(", ")}` : ""}
                </Text>
              ) : e.evidence.length ? (
                <Text style={styles.meta}>{e.evidence.join(", ")}</Text>
              ) : null}
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  table: { gap: 2 },
  title: { fontSize: font.body, fontWeight: "700", color: colors.text, marginBottom: space.xs },
  row: {
    flexDirection: "row",
    gap: space.sm,
    paddingVertical: space.xs,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  pressed: { backgroundColor: "#EEF3F7" },
  status: { width: 18, fontSize: font.small, fontWeight: "800", textAlign: "center" },
  id: { width: 26, fontSize: font.small, fontWeight: "700", color: colors.text },
  body: { flex: 1 },
  name: { fontSize: font.small, color: colors.text, fontWeight: "600" },
  value: { fontWeight: "400" },
  detail: { fontSize: 14, color: colors.textMuted },
  meta: { fontSize: 13, color: colors.textMuted },
});
