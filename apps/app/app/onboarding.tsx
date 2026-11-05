// Voice onboarding (spec §7.4, prompt §10.8), under a minute: language first → harbour → boat (three picture
// buttons) → spoken consent + "Turn on alerts" (Google sign-in, then the notification prompt) or "Not now".
// Public use needs no login (rule 7); the permission prompt never appears before "Turn on alerts".
import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet } from "react-native";
import { Text } from "../src/ui/Text";

import { api, type BoatKind } from "../src/api/channels";
import { signInWithGoogle } from "../src/auth/google";
import { supabase, useSession } from "../src/auth/supabase";
import { LanguagePicker } from "../src/components/LanguagePicker";
import { availableLanguages, deviceLanguage, languageInfo } from "../src/i18n";
import { registerPush } from "../src/push/register";
import { usePrefs } from "../src/state/prefs";
import { colors, font, radius, space, touch } from "../src/ui/tokens";
import { hasVoice, speak } from "../src/voice/speak";

type Step = "language" | "harbour" | "suggest" | "boat" | "alerts";
const BOATS: { kind: BoatKind; icon: string }[] = [
  { kind: "non_motorised", icon: "🛶" },
  { kind: "small_frp", icon: "🚤" },
  { kind: "mechanised_trawler", icon: "🚢" },
];

export default function Onboarding() {
  const { t } = useTranslation();
  const params = useLocalSearchParams<{ step?: Step }>();
  const { prefs, lang, update } = usePrefs();
  const { session } = useSession();
  const [step, setStep] = useState<Step>(params.step ?? "language");
  const [status, setStatus] = useState<"idle" | "working" | "done" | "failed">("idle");
  const [suggested, setSuggested] = useState<{ code: string; harbour: string } | null>(null);
  const harbours = useQuery({ queryKey: ["harbours"], queryFn: api.harbours, enabled: step === "harbour" });
  const consent = useQuery({ queryKey: ["consent", lang], queryFn: () => api.consent(lang), enabled: step === "alerts" });

  // spoken consent (15 s) where the language has a voice
  useEffect(() => {
    if (step === "alerts" && consent.data && hasVoice(lang)) void speak(consent.data.short, lang);
  }, [step, consent.data, lang]);

  // web: back from the Google redirect with a session → finish turning alerts on
  useEffect(() => {
    if (params.step === "alerts" && session && status === "idle" && prefs.harbour && prefs.boatKind) void finish();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  async function finish() {
    setStatus("working");
    try {
      let token = (await supabase().auth.getSession()).data.session?.access_token;
      if (!token) {
        await update({}); // keep the choices across the web redirect
        const done = await signInWithGoogle("/onboarding?step=alerts");
        if (!done) return; // web: the page redirects; we come back to /onboarding?step=alerts
        token = (await supabase().auth.getSession()).data.session?.access_token;
      }
      if (!token) throw new Error("not signed in");
      const c = consent.data ?? (await api.consent(lang));
      await api.onboarding(token, {
        language: lang,
        harbour: prefs.harbour!,
        boat_kind: prefs.boatKind!,
        consents: ["location_alerts", "voice_processing"],
        notice_version: c.notice_version,
      });
      const pushOn = await registerPush(token);
      await update({ onboarded: true, alertsOn: pushOn });
      setStatus("done");
      router.replace("/");
    } catch {
      setStatus("failed");
    }
  }

  async function skip() {
    await update({ onboarded: true });
    router.replace("/");
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content} testID={`onboarding-${step}`}>
      <Text style={styles.brand}>{t("app.title")}</Text>

      {step === "language" ? (
        <>
          <Text style={styles.title} accessibilityRole="header">
            {t("lang.title")}
          </Text>
          <LanguagePicker
            suggested={prefs.lang ?? deviceLanguage()}
            onPicked={async (code) => {
              await update({ lang: code });
              setStep("harbour");
            }}
          />
        </>
      ) : null}

      {step === "harbour" ? (
        <>
          <Text style={styles.title} accessibilityRole="header">
            {t("onboarding.harbour.title")}
          </Text>
          {harbours.isLoading ? <ActivityIndicator color={colors.text} /> : null}
          {(harbours.data ?? []).map((h) => (
            <Pressable
              key={h.id}
              style={[styles.choice, prefs.harbour === h.id && styles.chosen]}
              onPress={async () => {
                await update({ harbour: h.id });
                // spec §6.5: suggest the language of the harbour's state, accept any other
                const s = h.suggested_language;
                const offered = s && s !== lang && availableLanguages().some((l) => l.code === s);
                setSuggested(offered ? { code: s, harbour: h.name } : null);
                setStep(offered ? "suggest" : "boat");
              }}
              accessibilityRole="button"
              accessibilityLabel={h.name}
              testID={`harbour-${h.id}`}
            >
              <Text style={styles.choiceText}>⚓ {h.name}</Text>
            </Pressable>
          ))}
          <Back onPress={() => setStep("language")} />
        </>
      ) : null}

      {step === "suggest" && suggested ? (
        <>
          <Text style={styles.title} accessibilityRole="header">
            {t("onboarding.suggest.title", { harbour: suggested.harbour })}
          </Text>
          {[suggested.code, lang].map((code) => (
            <Pressable
              key={code}
              style={[styles.choice, code === lang && styles.chosen]}
              onPress={async () => {
                if (code !== lang) await update({ lang: code });
                setStep("boat");
              }}
              accessibilityRole="button"
              accessibilityLabel={languageInfo(code)?.name ?? code}
              accessibilityLanguage={code}
              testID={code === lang ? "suggest-keep" : "suggest-switch"}
            >
              <Text style={styles.choiceText} lang={code}>
                {languageInfo(code)?.name ?? code}
              </Text>
            </Pressable>
          ))}
          <Back onPress={() => setStep("harbour")} />
        </>
      ) : null}

      {step === "boat" ? (
        <>
          <Text style={styles.title} accessibilityRole="header">
            {t("onboarding.boat.title")}
          </Text>
          {BOATS.map((b) => (
            <Pressable
              key={b.kind}
              style={[styles.boat, prefs.boatKind === b.kind && styles.chosen]}
              onPress={async () => {
                await update({ boatKind: b.kind });
                setStep("alerts");
              }}
              accessibilityRole="button"
              accessibilityLabel={t(`onboarding.boat.${b.kind}`)}
              testID={`boat-${b.kind}`}
            >
              <Text style={styles.boatIcon} importantForAccessibility="no">
                {b.icon}
              </Text>
              <Text style={styles.choiceText}>{t(`onboarding.boat.${b.kind}`)}</Text>
            </Pressable>
          ))}
          <Back onPress={() => setStep("harbour")} />
        </>
      ) : null}

      {step === "alerts" ? (
        <>
          <Text style={styles.title} accessibilityRole="header">
            {t("onboarding.alerts.title")}
          </Text>
          {consent.data ? (
            <Text style={styles.body} testID="consent-short">
              {consent.data.short}
            </Text>
          ) : (
            <ActivityIndicator color={colors.text} />
          )}
          <Pressable onPress={() => router.push("/notice")} accessibilityRole="link" testID="read-notice">
            <Text style={styles.link}>{t("me.notice")}</Text>
          </Pressable>
          <Pressable
            style={styles.primary}
            onPress={() => void finish()}
            disabled={status === "working" || !consent.data}
            accessibilityRole="button"
            accessibilityLabel={t("onboarding.alerts.turnOn")}
            testID="turn-on-alerts"
          >
            {status === "working" ? (
              <ActivityIndicator color={colors.background} />
            ) : (
              <Text style={styles.primaryText}>🔔 {t("onboarding.alerts.turnOn")}</Text>
            )}
          </Pressable>
          {status === "failed" ? <Text style={styles.body}>{t("onboarding.alerts.failed")}</Text> : null}
          <Pressable
            style={styles.choice}
            onPress={() => void skip()}
            accessibilityRole="button"
            accessibilityLabel={t("onboarding.alerts.skip")}
            testID="alerts-not-now"
          >
            <Text style={styles.choiceText}>{t("onboarding.alerts.skip")}</Text>
          </Pressable>
          <Back onPress={() => setStep("boat")} />
        </>
      ) : null}
    </ScrollView>
  );
}

function Back({ onPress }: { onPress: () => void }) {
  const { t } = useTranslation();
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={t("onboarding.back")} testID="onboarding-back">
      <Text style={styles.link}>← {t("onboarding.back")}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  content: { padding: space.lg, gap: space.md },
  brand: { fontSize: font.body, color: colors.textMuted, fontWeight: "700" },
  title: { fontSize: font.title, color: colors.text, fontWeight: "700" },
  body: { fontSize: font.body, color: colors.text },
  link: { fontSize: font.body, color: colors.link, textDecorationLine: "underline", paddingVertical: space.sm },
  choice: {
    minHeight: touch.min,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: space.md,
    justifyContent: "center",
  },
  chosen: { borderWidth: 4 },
  choiceText: { fontSize: font.body + 2, color: colors.text, fontWeight: "600" },
  boat: {
    minHeight: 96,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.md,
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    paddingHorizontal: space.md,
  },
  boatIcon: { fontSize: 48 },
  primary: {
    minHeight: touch.min + 16,
    borderRadius: radius.md,
    backgroundColor: colors.text,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryText: { color: colors.background, fontSize: font.body + 2, fontWeight: "700" },
});
