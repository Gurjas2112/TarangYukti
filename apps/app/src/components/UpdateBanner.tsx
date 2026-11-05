// Update prompts (spec §17.12): a banner when a newer APK exists, a full-screen prompt below minVersionCode.
// Alerts keep working either way: the prompt links to the Alerts tab, and background tasks are not touched.
// Android only: the web build is always current.
import { useQuery } from "@tanstack/react-query";
import * as Application from "expo-application";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { Linking, Modal, Platform, Pressable, StyleSheet, View } from "react-native";

import { api } from "../api/channels";
import { Text } from "../ui/Text";
import { colors, font, radius, space, touch } from "../ui/tokens";

export function UpdateBanner() {
  const { t } = useTranslation();
  const v = useQuery({ queryKey: ["app-version"], queryFn: api.appVersion, enabled: Platform.OS === "android" });
  const current = Number(Application.nativeBuildVersion ?? "0");
  if (Platform.OS !== "android" || !v.data || !current) return null;
  const open = () => (v.data?.apkUrl ? void Linking.openURL(v.data.apkUrl) : undefined);

  if (current < v.data.minVersionCode) {
    return (
      <Modal visible animationType="fade" onRequestClose={() => router.push("/alerts")}>
        <View style={styles.full} testID="update-required">
          <Text style={styles.title} accessibilityRole="header">
            {t("update.required.title")}
          </Text>
          <Text style={styles.body}>{t("update.required.body")}</Text>
          {v.data.apkUrl ? (
            <Pressable style={styles.primary} onPress={open} accessibilityRole="button" testID="update-download">
              <Text style={styles.primaryText}>{t("update.download")}</Text>
            </Pressable>
          ) : null}
          <Pressable
            style={styles.secondary}
            onPress={() => router.push("/alerts")}
            accessibilityRole="button"
            testID="update-alerts"
          >
            <Text style={styles.secondaryText}>{t("update.openAlerts")}</Text>
          </Pressable>
        </View>
      </Modal>
    );
  }
  if (current < v.data.latestVersionCode) {
    return (
      <View style={styles.banner} testID="update-banner" accessibilityLiveRegion="polite">
        <Text style={styles.bannerText}>{t("update.available")}</Text>
        {v.data.apkUrl ? (
          <Pressable onPress={open} accessibilityRole="button" style={styles.link} testID="update-download">
            <Text style={styles.linkText}>{t("update.download")}</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }
  return null;
}

const styles = StyleSheet.create({
  full: { flex: 1, backgroundColor: colors.background, padding: space.lg, gap: space.lg, justifyContent: "center" },
  title: { fontSize: font.title, fontWeight: "700", color: colors.text },
  body: { fontSize: font.body, color: colors.text },
  primary: { minHeight: touch.min, backgroundColor: colors.text, borderRadius: radius.md, justifyContent: "center" },
  primaryText: { color: colors.background, fontSize: font.body, fontWeight: "700", textAlign: "center" },
  secondary: { minHeight: touch.min, borderWidth: 2, borderColor: colors.border, borderRadius: radius.md, justifyContent: "center" },
  secondaryText: { color: colors.text, fontSize: font.body, fontWeight: "700", textAlign: "center" },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: space.sm,
  },
  bannerText: { flex: 1, fontSize: font.body, color: colors.text },
  link: { minHeight: touch.min, justifyContent: "center", paddingHorizontal: space.sm },
  linkText: { fontSize: font.body, fontWeight: "700", color: colors.link },
});
