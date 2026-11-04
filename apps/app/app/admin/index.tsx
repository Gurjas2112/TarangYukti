// Staff consoles are web screens (spec §17.9): the Android build shows where to open them instead.
import { useTranslation } from "react-i18next";
import { StyleSheet, Text, View } from "react-native";

import { colors, font, space } from "../../src/ui/tokens";
import { EXPERT_URL } from "../expert";

export default function AdminFallback() {
  const { t } = useTranslation();
  return (
    <View style={styles.root} testID="admin-open-on-computer">
      <Text style={styles.body}>{t("web.openOnComputer", { url: EXPERT_URL.replace("/expert", "/admin") })}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, padding: space.lg, justifyContent: "center", backgroundColor: colors.background },
  body: { fontSize: font.body, color: colors.text, textAlign: "center" },
});
