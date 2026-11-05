// The Expert console is a web screen (spec §17.9): the Android build shows where to open it instead.
import { useTranslation } from "react-i18next";
import { StyleSheet, View } from "react-native";
import { Text } from "../../src/ui/Text";

import { colors, font, space } from "../../src/ui/tokens";

export const EXPERT_URL = "https://<web host>/expert"; // TODO(tarangyukti): the Front Door web host (Milestone 10)

export default function ExpertFallback() {
  const { t } = useTranslation();
  return (
    <View style={styles.root} testID="expert-open-on-computer">
      <Text style={styles.body}>{t("web.openOnComputer", { url: EXPERT_URL })}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, padding: space.lg, justifyContent: "center", backgroundColor: colors.background },
  body: { fontSize: font.body, color: colors.text, textAlign: "center" },
});
