import { useState } from "react";
import { useTranslation } from "react-i18next";
import { FlatList, Modal, Pressable, StyleSheet, Text, View } from "react-native";

import { availableLanguages, type Language } from "../i18n";
import { usePrefs } from "../state/prefs";
import { colors, font, radius, space, touch } from "../ui/tokens";
import { hasVoice, speak } from "../voice/speak";

/** Every available language in its own script (spec §6.5); 🔊 speaks the name where a voice exists. */
export function LanguagePicker({ onPicked, suggested }: { onPicked: (code: string) => void; suggested?: string | null }) {
  const { t } = useTranslation();
  const langs = [...availableLanguages()].sort((a, b) =>
    a.code === suggested ? -1 : b.code === suggested ? 1 : 0,
  );
  const row = ({ item }: { item: Language }) => (
    <View style={styles.row}>
      <Pressable
        style={[styles.lang, item.code === suggested && styles.suggested]}
        onPress={() => onPicked(item.code)}
        accessibilityRole="button"
        accessibilityLabel={item.name}
        accessibilityLanguage={item.code}
        testID={`lang-${item.code}`}
      >
        <Text style={styles.name}>{item.name}</Text>
        {item.status === "draft" ? <Text style={styles.draft}>{t("lang.draft")}</Text> : null}
      </Pressable>
      {hasVoice(item.code) ? (
        <Pressable
          style={styles.speak}
          onPress={() => void speak(item.name, item.code)}
          accessibilityRole="button"
          accessibilityLabel={`🔊 ${item.name}`}
          testID={`lang-speak-${item.code}`}
        >
          <Text style={styles.name}>🔊</Text>
        </Pressable>
      ) : null}
    </View>
  );
  return <FlatList data={langs} keyExtractor={(l) => l.code} renderItem={row} contentContainerStyle={styles.list} />;
}

/** The language button that stays on every screen. */
export function LanguageButton() {
  const { t } = useTranslation();
  const { lang, update } = usePrefs();
  const [open, setOpen] = useState(false);
  const [restart, setRestart] = useState(false);
  const name = availableLanguages().find((l) => l.code === lang)?.name ?? lang;
  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        style={styles.button}
        accessibilityRole="button"
        accessibilityLabel={`${t("lang.button")}: ${name}`}
        testID="language-button"
      >
        <Text style={styles.buttonText}>🌐 {name}</Text>
      </Pressable>
      <Modal visible={open} animationType="slide" onRequestClose={() => setOpen(false)}>
        <View style={styles.modal}>
          <Text style={styles.title} accessibilityRole="header">
            {t("lang.title")}
          </Text>
          {restart ? <Text style={styles.draft}>{t("lang.restart")}</Text> : null}
          <LanguagePicker
            suggested={lang}
            onPicked={async (code) => {
              const r = await update({ lang: code });
              setRestart(r.restart);
              setOpen(false);
            }}
          />
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  list: { gap: space.sm, paddingBottom: space.xl },
  row: { flexDirection: "row", gap: space.sm },
  lang: {
    flex: 1,
    minHeight: touch.min,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: space.md,
    justifyContent: "center",
  },
  suggested: { borderWidth: 4 },
  speak: {
    width: touch.min + 8,
    minHeight: touch.min,
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  name: { fontSize: font.title - 4, color: colors.text },
  draft: { fontSize: font.small, color: colors.textMuted },
  button: { minHeight: touch.min, justifyContent: "center", paddingHorizontal: space.sm },
  buttonText: { fontSize: font.body, color: colors.text, fontWeight: "600" },
  modal: { flex: 1, backgroundColor: colors.background, padding: space.lg, gap: space.md },
  title: { fontSize: font.title, fontWeight: "700", color: colors.text },
});
