// Me → Help (spec §9.5): who to contact with a grievance or a data request, in the user's language, plus what the
// system does and does not do. Contacts come from config/governance.yaml via channels /help.
import { useQuery } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { useTranslation } from "react-i18next";
import { Linking, Pressable, ScrollView, StyleSheet } from "react-native";
import { Text } from "../src/ui/Text";

import { api } from "../src/api/channels";
import { colors, font, space } from "../src/ui/tokens";

export default function Help() {
  const { t } = useTranslation();
  const help = useQuery({ queryKey: ["help"], queryFn: api.help });
  const g = help.data;
  return (
    <>
      <Stack.Screen options={{ headerShown: true, title: t("help.title") }} />
      <ScrollView contentContainerStyle={styles.root} testID="help-screen">
        <Text style={styles.h}>{t("help.grievance")}</Text>
        {g ? (
          <>
            <Text style={styles.body} testID="grievance-name">
              {g.grievance_officer.name}
            </Text>
            <Pressable onPress={() => void Linking.openURL(`mailto:${g.grievance_officer.email}`)} accessibilityRole="link">
              <Text style={styles.link} testID="grievance-email">
                {g.grievance_officer.email}
              </Text>
            </Pressable>
            <Text style={styles.body}>{t("help.times", { reply: g.response_days, erase: g.erasure_days })}</Text>
          </>
        ) : null}
        <Text style={styles.h}>{t("help.whatItIs")}</Text>
        <Text style={styles.body}>{t("help.whatItIsBody")}</Text>
        <Text style={styles.body}>{t("footer")}</Text>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  root: { padding: space.lg, gap: space.sm, backgroundColor: colors.background, flexGrow: 1 },
  h: { fontSize: font.body + 2, fontWeight: "800", color: colors.text, marginTop: space.sm },
  body: { fontSize: font.body, color: colors.text, lineHeight: font.body * 1.4 },
  link: { fontSize: font.body, color: colors.link, textDecorationLine: "underline" },
});
