import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "../ui/Text";

import { colors, font, radius, space, touch } from "../ui/tokens";

export type ButtonId = "today" | "fish" | "alerts" | "back";
const ICONS: Record<ButtonId, string> = { today: "🌊", fish: "🐟", alerts: "🔔", back: "⚓" };
const IDS: ButtonId[] = ["today", "fish", "alerts", "back"];

/** The four daily buttons (prompt §10.2): Today's sea · Where to fish · Alerts · I'm back. Icons always with words. */
export function FourButtons({ onPress }: { onPress: (id: ButtonId) => void }) {
  const { t } = useTranslation();
  return (
    <View style={styles.grid} testID="four-buttons">
      {IDS.map((id) => (
        <Pressable
          key={id}
          onPress={() => onPress(id)}
          style={({ pressed }) => [styles.button, pressed && styles.pressed]}
          accessibilityRole="button"
          accessibilityLabel={t(`buttons.${id}`)}
          testID={`button-${id}`}
        >
          <Text style={styles.icon} importantForAccessibility="no">
            {ICONS[id]}
          </Text>
          <Text style={styles.label}>{t(`buttons.${id}`)}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  button: {
    flexBasis: "48%",
    flexGrow: 1,
    minHeight: touch.min + 16,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: space.sm,
    padding: space.sm,
    backgroundColor: colors.background,
  },
  pressed: { backgroundColor: "#E6E6E6" },
  icon: { fontSize: font.body + 4 },
  label: { fontSize: font.body, color: colors.text, fontWeight: "700", flexShrink: 1 },
});
