// Alerts tab: today's pushes for the signed-in user (RLS: own rows only) and the quiet hours.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { z } from "zod";

import { api } from "../../src/api/channels";
import { supabase, useSession } from "../../src/auth/supabase";
import { colors, font, radius, space } from "../../src/ui/tokens";

const Row = z.object({
  id: z.string(),
  kind: z.string(),
  critical: z.boolean(),
  title: z.string(),
  body: z.string(),
  created_at: z.string(),
});

export default function AlertsTab() {
  const { t } = useTranslation();
  const { session } = useSession();
  const token = session?.access_token;
  const alerts = useQuery({
    queryKey: ["alerts", session?.user.id],
    enabled: Boolean(token),
    queryFn: async () => {
      const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
      const { data, error } = await supabase()
        .from("alerts")
        .select("id, kind, critical, title, body, created_at")
        .gte("created_at", since)
        .neq("status", "suppressed")
        .order("created_at", { ascending: false });
      if (error) throw error;
      return z.array(Row).parse(data);
    },
  });
  const me = useQuery({ queryKey: ["me", session?.user.id], enabled: Boolean(token), queryFn: () => api.me(token!) });

  if (!token) {
    return (
      <View style={styles.root} testID="alerts-screen">
        <Text style={styles.body}>{t("alerts.signIn")}</Text>
      </View>
    );
  }
  const prefs = me.data?.prefs;
  return (
    <ScrollView contentContainerStyle={styles.root} testID="alerts-screen">
      {prefs ? <Text style={styles.muted}>{t("alerts.quiet", { from: prefs.quiet_from, to: prefs.quiet_to })}</Text> : null}
      {alerts.data?.length === 0 ? <Text style={styles.body}>{t("alerts.none")}</Text> : null}
      {alerts.data?.map((a) => (
        <View key={a.id} style={[styles.card, a.critical && styles.critical]} testID={`alert-${a.kind}`}>
          <Text style={styles.title}>
            {a.critical ? `⚠ ${t("alerts.critical")} · ` : ""}
            {a.title}
          </Text>
          <Text style={styles.body}>{a.body}</Text>
          <Text style={styles.muted}>
            {new Date(a.created_at).toLocaleTimeString("en-IN", {
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
              timeZone: "Asia/Kolkata",
            })}
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { padding: space.lg, gap: space.md, backgroundColor: colors.background, flexGrow: 1 },
  body: { fontSize: font.body, color: colors.text },
  muted: { fontSize: font.small, color: colors.textMuted },
  title: { fontSize: font.body, color: colors.text, fontWeight: "700" },
  card: { borderWidth: 2, borderColor: colors.border, borderRadius: radius.sm, padding: space.md, gap: space.xs },
  critical: { borderColor: colors.noGo, borderWidth: 4 },
});
