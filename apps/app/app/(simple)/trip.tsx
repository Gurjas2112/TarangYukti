// Trip tab (prompt §10.5–10.6): at sea since, distance to the border line, "I'm back", then "Was today's advice
// right?" 👍 / 👎 and "Right on N of the last M days". Trips open and close on the server from live positions.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";
import { Text } from "../../src/ui/Text";

import { api } from "../../src/api/channels";
import { useSession } from "../../src/auth/supabase";
import { TripLocal } from "../../src/components/TripLocal";
import { useLive } from "../../src/location/useLiveTracking";
import { stopTrip } from "../../src/tasks/trip";
import { colors, font, radius, space, touch } from "../../src/ui/tokens";

const hhmm = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

export default function TripTab() {
  const { t } = useTranslation();
  const { session } = useSession();
  const token = session?.access_token;
  const live = useLive();
  const qc = useQueryClient();
  const trips = useQuery({
    queryKey: ["trips", session?.user.id],
    queryFn: () => api.trips(token!),
    enabled: Boolean(token),
    refetchInterval: 60_000,
  });
  const [thanks, setThanks] = useState(false);

  if (!token) {
    return (
      <View style={styles.root} testID="trip-screen">
        <Text style={styles.body}>{t("trip.needsSignIn")}</Text>
      </View>
    );
  }
  const open = trips.data?.open ?? null;
  const lastClosed = trips.data?.closed[0];
  const askFeedback = !open && lastClosed && !lastClosed.feedback && !thanks;
  const ro = trips.data?.right_on;

  async function back() {
    await stopTrip(); // the phone's trip mode stops too (the harbour geofence restarts it next time)
    await api.back(token!);
    await qc.invalidateQueries({ queryKey: ["trips"] });
  }
  async function vote(v: "right" | "wrong") {
    if (!lastClosed) return;
    await api.feedback(token!, lastClosed.id, v);
    setThanks(true);
    await qc.invalidateQueries({ queryKey: ["trips"] });
  }

  return (
    <ScrollView contentContainerStyle={styles.root} testID="trip-screen">
      <TripLocal />
      {open ? (
        <View style={styles.card} testID="trip-open" accessibilityLiveRegion="polite">
          <Text style={styles.big}>⛵ {t("trip.atSeaSince", { time: hhmm(open.departed_at) })}</Text>
          {live.last ? (
            <Text style={[styles.body, live.last.border.ring !== "clear" && styles.danger]} testID="trip-border">
              🚩 {t("trip.borderKm", { km: live.last.border.km })}
            </Text>
          ) : null}
          <Pressable
            style={styles.primary}
            onPress={() => void back()}
            accessibilityRole="button"
            accessibilityLabel={t("trip.back")}
            testID="trip-im-back"
          >
            <Text style={styles.primaryText}>⚓ {t("trip.back")}</Text>
          </Pressable>
        </View>
      ) : (
        <Text style={styles.body} testID="trip-none">
          {lastClosed?.returned_at ? t("trip.backAt", { time: hhmm(lastClosed.returned_at) }) : t("trip.notAtSea")}
        </Text>
      )}

      {askFeedback ? (
        <View style={styles.card} testID="trip-feedback">
          <Text style={styles.big}>{t("trip.feedbackAsk")}</Text>
          <View style={styles.row}>
            <Pressable style={styles.vote} onPress={() => void vote("right")} accessibilityRole="button" accessibilityLabel={t("trip.right")} testID="feedback-right">
              <Text style={styles.voteText}>👍 {t("trip.right")}</Text>
            </Pressable>
            <Pressable style={styles.vote} onPress={() => void vote("wrong")} accessibilityRole="button" accessibilityLabel={t("trip.wrong")} testID="feedback-wrong">
              <Text style={styles.voteText}>👎 {t("trip.wrong")}</Text>
            </Pressable>
          </View>
        </View>
      ) : null}
      {thanks ? <Text style={styles.body}>{t("trip.thanks")}</Text> : null}
      {ro && ro.total > 0 ? (
        <Text style={styles.body} testID="trip-right-on">
          {t("trip.rightOn", { right: ro.right, total: ro.total })}
        </Text>
      ) : null}
      {live.error === "permission" ? <Text style={styles.note}>{t("trip.locationOff")}</Text> : null}
      {live.error === "outside" ? <Text style={styles.note}>{t("trip.outsideRegion")}</Text> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { padding: space.lg, gap: space.md, backgroundColor: colors.background, flexGrow: 1 },
  card: { borderWidth: 2, borderColor: colors.border, borderRadius: radius.md, padding: space.md, gap: space.sm },
  big: { fontSize: font.title - 4, fontWeight: "700", color: colors.text },
  body: { fontSize: font.body, color: colors.text },
  danger: { color: colors.noGo, fontWeight: "800" },
  note: { fontSize: font.small, color: colors.textMuted },
  row: { flexDirection: "row", gap: space.sm },
  vote: { flex: 1, minHeight: touch.min + 8, borderWidth: 2, borderColor: colors.border, borderRadius: radius.sm, alignItems: "center", justifyContent: "center" },
  voteText: { fontSize: font.body + 2, color: colors.text, fontWeight: "700" },
  primary: { minHeight: touch.min + 16, borderRadius: radius.md, backgroundColor: colors.text, alignItems: "center", justifyContent: "center" },
  primaryText: { color: colors.background, fontSize: font.body + 2, fontWeight: "700" },
});
