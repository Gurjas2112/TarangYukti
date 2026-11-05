// Me → family (spec §9.1.3): share my boat with a family member's e-mail (up to 90 days), see who accepted, revoke;
// and the boats shared with me, each opening its family card.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, TextInput, View } from "react-native";
import { Text } from "../ui/Text";

import { api, ApiError } from "../api/channels";
import { colors, font, radius, space, touch } from "../ui/tokens";

export function FamilySharing({ token, boatId }: { token: string; boatId: string | null }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const grants = useQuery({ queryKey: ["shares"], queryFn: () => api.shares(token), enabled: Boolean(boatId) });
  const shared = useQuery({ queryKey: ["family"], queryFn: () => api.family(token) });

  async function share() {
    if (!boatId || !email.trim()) return;
    try {
      await api.share(token, boatId, email.trim());
      setEmail("");
      setNote(t("family.shared"));
      await qc.invalidateQueries({ queryKey: ["shares"] });
    } catch (e) {
      setNote(e instanceof ApiError && e.status === 422 ? t("family.badEmail") : t("family.failed"));
    }
  }

  return (
    <View style={styles.box} testID="family-sharing">
      {boatId ? (
        <>
          <Text style={styles.label}>{t("family.shareTitle")}</Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            placeholder={t("family.emailPlaceholder")}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            style={styles.input}
            accessibilityLabel={t("family.emailPlaceholder")}
            testID="share-email"
          />
          <Pressable style={styles.button} onPress={() => void share()} accessibilityRole="button" testID="share-boat">
            <Text style={styles.buttonText}>👪 {t("family.share")}</Text>
          </Pressable>
          {note ? <Text style={styles.small}>{note}</Text> : null}
          {(grants.data ?? [])
            .filter((g) => !g.revoked_at)
            .map((g) => (
              <View key={g.id} style={styles.row} testID={`grant-${g.id}`}>
                <Text style={styles.small}>
                  {g.grantee_email} · {g.accepted ? t("family.accepted") : t("family.pending")} · {t("family.until")}{" "}
                  {g.expires_at.slice(0, 10)}
                </Text>
                <Pressable
                  onPress={() => void api.revokeShare(token, g.id).then(() => qc.invalidateQueries({ queryKey: ["shares"] }))}
                  accessibilityRole="button"
                  accessibilityLabel={t("family.revoke")}
                >
                  <Text style={styles.link}>{t("family.revoke")}</Text>
                </Pressable>
              </View>
            ))}
        </>
      ) : null}
      {shared.data?.length ? (
        <>
          <Text style={styles.label}>{t("family.sharedWithMe")}</Text>
          {shared.data.map((b) => (
            <Pressable
              key={b.boat_id}
              style={styles.button}
              onPress={() => router.push(`/family/${b.boat_id}`)}
              accessibilityRole="button"
              testID={`family-boat-${b.boat_id}`}
            >
              <Text style={styles.buttonText}>
                {b.at_sea ? "⛵" : "⚓"} {b.name}
              </Text>
            </Pressable>
          ))}
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { gap: space.sm },
  label: { fontSize: font.small, color: colors.textMuted, fontWeight: "700" },
  input: { minHeight: touch.min, borderWidth: 2, borderColor: colors.border, borderRadius: radius.sm, paddingHorizontal: space.sm, fontSize: font.body },
  button: { minHeight: touch.min, borderWidth: 2, borderColor: colors.border, borderRadius: radius.sm, paddingHorizontal: space.md, justifyContent: "center" },
  buttonText: { fontSize: font.body, color: colors.text, fontWeight: "700" },
  row: { flexDirection: "row", gap: space.sm, alignItems: "center", flexWrap: "wrap" },
  small: { fontSize: font.small, color: colors.text },
  link: { fontSize: font.small, color: colors.link, textDecorationLine: "underline" },
});
