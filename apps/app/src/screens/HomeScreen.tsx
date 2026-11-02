import { StyleSheet, Text, View } from "react-native";

import { t } from "../i18n";
import { colors, font, space } from "../ui/tokens";

/** Milestone 1 placeholder. Milestone 6 replaces it with the Simple tabs (Today · Map · Trip · Alerts · Me). */
export function HomeScreen({ lang }: { lang?: string }) {
  return (
    <View style={styles.root} testID="home">
      <Text style={styles.title} accessibilityRole="header">
        {t("app.title", lang)}
      </Text>
      <Text style={styles.body}>{t("app.subtitle", lang)}</Text>
      <Text style={styles.body} testID="home-not-ready">
        {t("home.notReady", lang)}
      </Text>
      <Text style={styles.footer}>{t("footer", lang)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
    padding: space.lg,
    gap: space.md,
    justifyContent: "center",
  },
  title: { color: colors.text, fontSize: font.title, fontWeight: "700" },
  body: { color: colors.text, fontSize: font.body },
  footer: { color: colors.textMuted, fontSize: font.small, marginTop: space.xl },
});
