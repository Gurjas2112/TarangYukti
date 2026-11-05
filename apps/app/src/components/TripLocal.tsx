// Android trip mode on this phone (spec §17.4): since when the background trip runs, and the position outbox
// (waiting to send, or all sent). Refreshes every 10 s; nothing on the web.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Platform, StyleSheet, View } from "react-native";

import * as outbox from "../offline/outbox";
import { tripActiveSince } from "../tasks/trip";
import { Text } from "../ui/Text";
import { colors, font, radius, space } from "../ui/tokens";

const hhmm = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

export function TripLocal() {
  const { t } = useTranslation();
  const [since, setSince] = useState<string | null>(null);
  const [waiting, setWaiting] = useState<number | null>(null);
  useEffect(() => {
    if (Platform.OS !== "android") return;
    let live = true;
    const tick = async () => {
      const [s, n] = await Promise.all([tripActiveSince(), outbox.sync().then(() => outbox.pending())]);
      if (live) {
        setSince(s);
        setWaiting(n);
      }
    };
    void tick();
    const id = setInterval(() => void tick(), 10_000);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, []);
  if (Platform.OS !== "android" || (since === null && !waiting)) return null;
  return (
    <View style={styles.box} accessibilityLiveRegion="polite">
      {since ? (
        <Text style={styles.text} testID="trip-active">
          📡 {t("trip.local.active", { time: hhmm(since) })}
        </Text>
      ) : null}
      {waiting ? (
        <Text style={styles.text} testID="outbox-pending">
          {t("trip.local.pending", { n: waiting })}
        </Text>
      ) : (
        <Text style={styles.text} testID="outbox-synced">
          ✓ {t("trip.local.synced")}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { gap: space.xs, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: space.sm },
  text: { fontSize: font.body, color: colors.text },
});
