// Hold to speak (prompt §10.4): on release, a short "checking the sea…" clip plays within a second (pre-fetched
// audio), the voice note goes to channels /stt (Sarvam Saaras), the text to the agent; the reply is shown and
// spoken (Group A languages). Audio is never stored.
import { RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder } from "expo-audio";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";

import { api } from "../api/channels";
import { useAsk } from "../copilot/useAsk";
import { audioUrl, speak } from "../voice/speak";
import { colors, font, radius, space, touch } from "../ui/tokens";

type Turn = { you: string; reply: string };

export function MicButton({ lang, token }: { lang: string; token?: string | null }) {
  const { t } = useTranslation();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const { ask, busy } = useAsk();
  const [state, setState] = useState<"idle" | "recording" | "working">("idle");
  const [turn, setTurn] = useState<Turn | null>(null);
  const [note, setNote] = useState<string | null>(null);

  // pre-fetch the acknowledgement clip so it can start right after release
  useEffect(() => {
    void audioUrl(t("today.loading"), lang).catch(() => null);
  }, [lang, t]);

  async function start() {
    setNote(null);
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) {
      setNote(t("mic.denied"));
      return;
    }
    await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
    await recorder.prepareToRecordAsync();
    recorder.record();
    setState("recording");
  }

  async function finish() {
    if (state !== "recording") return;
    setState("working");
    void speak(t("today.loading"), lang); // instant acknowledgement
    try {
      await recorder.stop();
      const uri = recorder.uri;
      if (!uri) throw new Error("no recording");
      const form = new FormData();
      if (Platform.OS === "web") {
        const blob = await (await fetch(uri)).blob();
        form.append("audio", blob, "voice.webm");
      } else {
        form.append("audio", { uri, name: "voice.m4a", type: "audio/mp4" } as unknown as Blob);
      }
      form.append("lang", lang);
      const heard = await api.stt(form, token);
      const reply = await ask(heard.text);
      setTurn({ you: heard.text, reply });
      if (reply) void speak(reply, lang);
    } catch {
      setNote(t("mic.needsNetwork"));
    } finally {
      await setAudioModeAsync({ allowsRecording: false });
      setState("idle");
    }
  }

  const label = state === "recording" ? t("mic.release") : t("mic.hold");
  return (
    <View style={styles.wrap}>
      <Pressable
        onPressIn={() => void start()}
        onPressOut={() => void finish()}
        disabled={state === "working" || busy}
        style={[styles.mic, state === "recording" && styles.recording]}
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityState={{ busy: state === "working" }}
        testID="mic-button"
      >
        <Text style={styles.micIcon} importantForAccessibility="no">
          🎤
        </Text>
        <Text style={styles.micText}>
          {state === "working" ? t("today.loading") : state === "recording" ? t("mic.listening") : label}
        </Text>
      </Pressable>
      {note ? (
        <Text style={styles.note} testID="mic-note">
          {note}
        </Text>
      ) : null}
      {turn ? (
        <View style={styles.turn} testID="chat-turn" accessibilityLiveRegion="polite">
          <Text style={styles.who}>{t("chat.you")}</Text>
          <Text style={styles.text}>{turn.you}</Text>
          <Text style={styles.who}>{t("chat.reply")}</Text>
          <Text style={styles.text} testID="chat-reply">
            {turn.reply}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: space.sm },
  mic: {
    minHeight: touch.min + 16,
    borderRadius: radius.md,
    backgroundColor: colors.text,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: space.sm,
  },
  recording: { backgroundColor: colors.noGo },
  micIcon: { fontSize: font.body + 4 },
  micText: { color: colors.background, fontSize: font.body, fontWeight: "700" },
  note: { fontSize: font.body, color: colors.text },
  turn: { gap: space.xs, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: space.sm },
  who: { fontSize: font.small, color: colors.textMuted, fontWeight: "700" },
  text: { fontSize: font.body, color: colors.text },
});
