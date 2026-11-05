// Shared boat card (spec Table 7-4): "At sea since 05:10" / "Back at harbour 14:20" and the latest advice.
// Visible only with an unexpired share grant (RLS); opened from the family push or Me → Shared with me.
import { useQuery } from "@tanstack/react-query";
import { Stack, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScrollView, StyleSheet, View } from "react-native";
import { Text } from "../../src/ui/Text";

import { api } from "../../src/api/channels";
import { useSession } from "../../src/auth/supabase";
import { colors, font, radius, space } from "../../src/ui/tokens";

const hhmm = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });

export default function FamilyCard() {
  const { t } = useTranslation();
  const { boatId } = useLocalSearchParams<{ boatId: string }>();
  const { session } = useSession();
  const token = session?.access_token;
  const boats = useQuery({ queryKey: ["family", session?.user.id], queryFn: () => api.family(token!), enabled: Boolean(token), refetchInterval: 60_000 });
  const b = boats.data?.find((x) => x.boat_id === boatId);
  return (
    <>
      <Stack.Screen options={{ headerShown: true, title: t("family.title") }} />
      <ScrollView contentContainerStyle={styles.root} testID="family-card">
        {!token ? <Text style={styles.body}>{t("family.signIn")}</Text> : null}
        {token && boats.data && !b ? <Text style={styles.body}>{t("family.notShared")}</Text> : null}
        {b ? (
          <View style={[styles.card, { borderColor: b.at_sea ? colors.caution : colors.go }]} accessibilityLiveRegion="polite">
            <Text style={styles.name}>{b.name}</Text>
            <Text style={styles.status} testID="family-status">
              {b.at_sea && b.departed_at
                ? `⛵ ${t("family.atSeaSince", { time: hhmm(b.departed_at) })}`
                : b.returned_at
                  ? `⚓ ${t("family.backAt", { harbour: b.harbour ?? "", time: hhmm(b.returned_at) })}`
                  : t("family.noTrips")}
            </Text>
            {b.advice_verdict ? <Text style={styles.body}>{t("family.advice", { verdict: t(`verdict.${b.advice_verdict}`) })}</Text> : null}
          </View>
        ) : null}
        <Text style={styles.footer}>{t("footer")}</Text>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  root: { padding: space.lg, gap: space.md, backgroundColor: colors.background, flexGrow: 1 },
  card: { borderWidth: 3, borderRadius: radius.md, padding: space.md, gap: space.sm },
  name: { fontSize: font.title, fontWeight: "800", color: colors.text },
  status: { fontSize: font.body + 2, fontWeight: "700", color: colors.text },
  body: { fontSize: font.body, color: colors.text },
  footer: { fontSize: font.small, color: colors.textMuted },
});
