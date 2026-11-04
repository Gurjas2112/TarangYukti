// Me → My data (DPDP, spec §9.4): download everything we hold about you; delete your account (7-day undo, then
// everything is erased). Both are audit-logged.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Platform, Pressable, Share, StyleSheet, Text, View } from "react-native";

import { api } from "../api/channels";
import { colors, font, radius, space, touch } from "../ui/tokens";

export function MyData({ token, deleting }: { token: string; deleting: string | null }) {
  const { t } = useTranslation();
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(deleting);

  async function download() {
    try {
      const json = await api.exportData(token);
      if (Platform.OS === "web") {
        const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = "tarangyukti-my-data.json";
        a.click();
        URL.revokeObjectURL(url);
      } else {
        await Share.share({ title: "TarangYukti — my data", message: json });
      }
      setNote(t("mydata.downloaded"));
    } catch {
      setNote(t("mydata.failed"));
    }
  }

  async function remove() {
    try {
      const r = await api.requestDelete(token);
      setPending(r.delete_after);
    } catch {
      setNote(t("mydata.failed"));
    }
  }

  async function undo() {
    await api.cancelDelete(token).catch(() => undefined);
    setPending(null);
  }

  return (
    <View style={styles.box} testID="my-data">
      <Pressable style={styles.button} onPress={() => void download()} accessibilityRole="button" testID="download-my-data">
        <Text style={styles.text}>⬇ {t("mydata.download")}</Text>
      </Pressable>
      {pending ? (
        <View style={styles.warn} testID="deletion-pending">
          <Text style={styles.small}>{t("mydata.deletingOn", { date: pending.slice(0, 10) })}</Text>
          <Pressable style={styles.button} onPress={() => void undo()} accessibilityRole="button" testID="cancel-delete">
            <Text style={styles.text}>{t("mydata.undo")}</Text>
          </Pressable>
        </View>
      ) : (
        <Pressable style={styles.danger} onPress={() => void remove()} accessibilityRole="button" testID="delete-account">
          <Text style={styles.dangerText}>{t("mydata.delete")}</Text>
        </Pressable>
      )}
      <Text style={styles.small}>{t("mydata.deleteHelp")}</Text>
      {note ? <Text style={styles.small}>{note}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { gap: space.sm },
  button: { minHeight: touch.min, borderWidth: 2, borderColor: colors.border, borderRadius: radius.sm, paddingHorizontal: space.md, justifyContent: "center" },
  text: { fontSize: font.body, color: colors.text, fontWeight: "700" },
  danger: { minHeight: touch.min, borderWidth: 2, borderColor: colors.noGo, borderRadius: radius.sm, paddingHorizontal: space.md, justifyContent: "center" },
  dangerText: { fontSize: font.body, color: colors.noGo, fontWeight: "700" },
  warn: { gap: space.xs, borderLeftWidth: 4, borderColor: colors.noGo, paddingLeft: space.sm },
  small: { fontSize: font.small, color: colors.text },
});
