import { useTranslation } from "react-i18next";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";

import type { Brief } from "../api/channels";
import { colors, font, radius, space, touch } from "../ui/tokens";

/** "Why?" — one plain sentence per reason (approved phrases). "See all reasons" is the Expert ledger
 * (Milestone 7); in Simple mode it lists every reason in plain words. */
export function WhySheet({ brief, open, onClose }: { brief: Brief; open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet} testID="why-sheet">
          <Text style={styles.title} accessibilityRole="header">
            {t("why.title")}
          </Text>
          {brief.why.length ? (
            brief.why.map((w) => (
              <Text key={w} style={styles.body}>
                • {w}
              </Text>
            ))
          ) : (
            <Text style={styles.body}>{t("why.none")}</Text>
          )}
          {brief.stale ? <Text style={styles.body}>• {brief.stale}</Text> : null}
          <Text style={styles.source}>{brief.sources.join(" · ")}</Text>
          <Text style={styles.footer}>{brief.footer}</Text>
          <Pressable
            style={styles.button}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel={t("why.close")}
            testID="why-close"
          >
            <Text style={styles.buttonText}>{t("why.close")}</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.4)" },
  sheet: {
    backgroundColor: colors.background,
    padding: space.lg,
    gap: space.sm,
    borderTopLeftRadius: radius.md,
    borderTopRightRadius: radius.md,
  },
  title: { fontSize: font.title, fontWeight: "700", color: colors.text },
  body: { fontSize: font.body, color: colors.text },
  source: { fontSize: font.small, color: colors.textMuted },
  footer: { fontSize: font.small, color: colors.textMuted },
  button: {
    minHeight: touch.min,
    borderRadius: radius.sm,
    backgroundColor: colors.text,
    alignItems: "center",
    justifyContent: "center",
    marginTop: space.sm,
  },
  buttonText: { color: colors.background, fontSize: font.body, fontWeight: "700" },
});
