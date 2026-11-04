// Me tab (spec §17.9): language, harbour and boat, sign in / out, alerts, "Add this phone", consents, notice.
// Family sharing, data download/delete and Help arrive in Milestones 8–9.
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import QRCode from "react-native-qrcode-svg";

import { api } from "../../src/api/channels";
import { signInWithGoogle } from "../../src/auth/google";
import { signOut, useSession } from "../../src/auth/supabase";
import { LanguageButton } from "../../src/components/LanguagePicker";
import { registerPush } from "../../src/push/register";
import { usePrefs } from "../../src/state/prefs";
import { colors, font, radius, space, touch } from "../../src/ui/tokens";

export default function MeTab() {
  const { t } = useTranslation();
  const { prefs, update } = usePrefs();
  const { session } = useSession();
  const token = session?.access_token;
  const me = useQuery({ queryKey: ["me", session?.user.id], enabled: Boolean(token), queryFn: () => api.me(token!) });
  const harbours = useQuery({ queryKey: ["harbours"], queryFn: api.harbours });
  const harbourName = harbours.data?.find((h) => h.id === prefs.harbour)?.name ?? prefs.harbour ?? "—";
  const [qr, setQr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function alertsOn() {
    if (!token) return;
    const ok = await registerPush(token).catch(() => false);
    await update({ alertsOn: ok });
    setNote(ok ? t("onboarding.alerts.done") : t("onboarding.alerts.failed"));
    void me.refetch();
  }

  return (
    <ScrollView contentContainerStyle={styles.root} testID="me-screen">
      <Section label={t("me.language")}>
        <LanguageButton />
      </Section>
      <Section label={t("me.harbour")}>
        <Text style={styles.value}>{harbourName}</Text>
      </Section>
      <Section label={t("me.boat")}>
        <Text style={styles.value}>{prefs.boatKind ? t(`onboarding.boat.${prefs.boatKind}`) : "—"}</Text>
      </Section>
      <Button
        id="me-redo-onboarding"
        label={t("me.redo")}
        onPress={() => {
          void update({ onboarded: false });
          router.replace("/onboarding");
        }}
      />

      {token ? (
        <>
          <Text style={styles.value}>✓ {t("me.signedInAs")}</Text>
          {me.data?.push.length ? (
            <Text style={styles.value} testID="alerts-on">
              🔔 {t("me.alertsOn")}
            </Text>
          ) : (
            <Button id="turn-on-alerts" label={`🔔 ${t("me.turnOnAlerts")}`} onPress={() => void alertsOn()} primary />
          )}
          <Button
            id="add-this-phone"
            label={`📱 ${t("me.addPhone")}`}
            onPress={async () => setQr((await api.phoneLink(token)).qr)}
          />
          {qr ? (
            <View style={styles.qr} testID="phone-link-qr">
              <QRCode value={qr} size={220} />
              <Text style={styles.small}>{t("me.addPhoneHelp")}</Text>
            </View>
          ) : null}
          {me.data?.consents.length ? (
            <Section label={t("me.consents")}>
              {me.data.consents.map((c) => (
                <Text key={`${c.purpose}-${c.given_at}`} style={styles.small}>
                  {c.purpose} · {c.notice_version} · {c.given_at.slice(0, 10)}
                </Text>
              ))}
            </Section>
          ) : null}
          <Button id="sign-out" label={t("me.signOut")} onPress={() => void signOut()} />
        </>
      ) : (
        <Button
          id="sign-in"
          label={t("me.signIn")}
          primary
          onPress={() => void signInWithGoogle("/me").catch(() => setNote(t("onboarding.alerts.failed")))}
        />
      )}
      {note ? <Text style={styles.value}>{note}</Text> : null}
      <Pressable onPress={() => router.push("/notice")} accessibilityRole="link" testID="read-notice">
        <Text style={styles.link}>{t("me.notice")}</Text>
      </Pressable>
    </ScrollView>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.label}>{label}</Text>
      {children}
    </View>
  );
}

function Button({ id, label, onPress, primary }: { id: string; label: string; onPress: () => void; primary?: boolean }) {
  return (
    <Pressable
      style={[styles.button, primary && styles.primary]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      testID={id}
    >
      <Text style={[styles.buttonText, primary && styles.primaryText]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { padding: space.lg, gap: space.md, backgroundColor: colors.background, flexGrow: 1 },
  section: { gap: space.xs },
  label: { fontSize: font.small, color: colors.textMuted, fontWeight: "700" },
  value: { fontSize: font.body, color: colors.text },
  small: { fontSize: font.small, color: colors.text },
  link: { fontSize: font.body, color: colors.link, textDecorationLine: "underline" },
  qr: { alignItems: "center", gap: space.sm, padding: space.md, backgroundColor: colors.background },
  button: {
    minHeight: touch.min,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: space.md,
    justifyContent: "center",
  },
  primary: { backgroundColor: colors.text },
  buttonText: { fontSize: font.body, color: colors.text, fontWeight: "700" },
  primaryText: { color: colors.background },
});
