import { router } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { api, type BoatKind } from "../api/channels";
import { useSession } from "../auth/supabase";
import { useBrief } from "../brief/useBrief";
import { type ButtonId, FourButtons } from "../components/FourButtons";
import { MicButton } from "../components/MicButton";
import { TimeRibbon } from "../components/TimeRibbon";
import { VerdictCard } from "../components/VerdictCard";
import { WhySheet } from "../components/WhySheet";
import { colors, font, radius, space, touch } from "../ui/tokens";
import { hasVoice, speak, stop } from "../voice/speak";

type Props = { harbour: string | null; boatKind: BoatKind | null; lang: string; autoplay?: boolean };

/** Today (spec §7.9): verdict card, 24-hour ribbon, "Why?", fish spot, border line, voice, the four buttons. */
export function TodayScreen({ harbour, boatKind, lang, autoplay = false }: Props) {
  const { t } = useTranslation();
  const { session } = useSession();
  const { brief, saved, loading, error, refetch } = useBrief(harbour, boatKind, lang);
  const [why, setWhy] = useState(false);
  const [playing, setPlaying] = useState(false);
  const autoplayed = useRef(false);

  // the morning brief opened from a push plays its voice once
  useEffect(() => {
    if (brief && autoplay && !autoplayed.current) {
      autoplayed.current = true;
      void speak(brief.speak, lang).then(setPlaying);
    }
  }, [brief, autoplay, lang]);

  function press(id: ButtonId) {
    if (id === "today") {
      refetch();
      if (brief) void speak(brief.speak, lang).then(setPlaying);
    } else if (id === "fish") router.push("/map");
    else if (id === "alerts") router.push("/alerts");
    else {
      if (session?.access_token) void api.back(session.access_token).catch(() => undefined);
      router.push("/trip");
    }
  }

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={styles.scroll} testID="today-screen">
        {loading && !brief ? (
          <View style={styles.center} accessibilityLiveRegion="polite">
            <ActivityIndicator size="large" color={colors.text} />
            <Text style={styles.body}>{t("today.loading")}</Text>
          </View>
        ) : null}
        {error ? (
          <Text style={styles.note} testID="today-offline">
            {brief ? t("today.error") : t("today.noSaved")}
          </Text>
        ) : null}
        {brief ? (
          <>
            <Text style={styles.meta}>
              {brief.harbour.name} · {brief.as_of ? t("today.asOf", { time: brief.as_of }) : ""}
              {saved ? ` · ${t("today.saved")}` : ""}
            </Text>
            <VerdictCard brief={brief} />
            <TimeRibbon ribbon={brief.ribbon} />
            {brief.spot ? (
              <Text style={styles.line} testID="today-spot">
                🐟 {brief.spot.text}
              </Text>
            ) : null}
            <Text style={styles.line} testID="today-border">
              🚩 {brief.border.text}
            </Text>
            {brief.stale ? <Text style={styles.note}>⏱ {brief.stale}</Text> : null}
            <View style={styles.actions}>
              <Pressable
                style={styles.secondary}
                onPress={() => setWhy(true)}
                accessibilityRole="button"
                accessibilityLabel={t("why.button")}
                testID="why-button"
              >
                <Text style={styles.secondaryText}>{t("why.button")}</Text>
              </Pressable>
              {hasVoice(lang) ? (
                <Pressable
                  style={styles.secondary}
                  onPress={() => {
                    if (playing) {
                      stop();
                      setPlaying(false);
                    } else void speak(brief.speak, lang).then(setPlaying);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={playing ? t("today.stop") : t("today.play")}
                  testID="play-brief"
                >
                  <Text style={styles.secondaryText}>{playing ? `■ ${t("today.stop")}` : `▶ ${t("today.play")}`}</Text>
                </Pressable>
              ) : null}
            </View>
            <Text style={styles.footer} testID="advisory-footer">
              {brief.footer}
            </Text>
            <WhySheet brief={brief} open={why} onClose={() => setWhy(false)} />
          </>
        ) : null}
        <MicButton lang={lang} token={session?.access_token} />
      </ScrollView>
      <View style={styles.bottom}>
        <FourButtons onPress={press} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  scroll: { padding: space.md, gap: space.md },
  center: { alignItems: "center", gap: space.sm, padding: space.lg },
  meta: { fontSize: font.small, color: colors.textMuted },
  body: { fontSize: font.body, color: colors.text },
  line: { fontSize: font.body + 2, color: colors.text, fontWeight: "600" },
  note: { fontSize: font.body, color: colors.text, borderLeftWidth: 4, borderColor: colors.caution, paddingLeft: space.sm },
  actions: { flexDirection: "row", gap: space.sm, flexWrap: "wrap" },
  secondary: {
    minHeight: touch.min,
    paddingHorizontal: space.md,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.sm,
    justifyContent: "center",
    flexShrink: 1,
    maxWidth: "100%",
  },
  secondaryText: { fontSize: font.body, color: colors.text, fontWeight: "700" },
  footer: { fontSize: font.small, color: colors.textMuted },
  bottom: { padding: space.sm, borderTopWidth: 1, borderColor: colors.border, backgroundColor: colors.background },
});
