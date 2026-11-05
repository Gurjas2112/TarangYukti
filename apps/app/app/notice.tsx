// The full written notice behind "Read full notice" (DPDP; spec §7.4). Draft wording until legal review (M9).
import { Stack } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScrollView, StyleSheet } from "react-native";
import { Text } from "../src/ui/Text";

import { colors, font, space } from "../src/ui/tokens";

export default function Notice() {
  const { t } = useTranslation();
  return (
    <>
      <Stack.Screen options={{ headerShown: true, title: t("notice.title") }} />
      <ScrollView contentContainerStyle={styles.root} testID="notice-screen">
        <Text style={styles.body}>{t("notice.body")}</Text>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  root: { padding: space.lg, backgroundColor: colors.background, flexGrow: 1 },
  body: { fontSize: font.body, color: colors.text, lineHeight: font.body * 1.5 },
});
