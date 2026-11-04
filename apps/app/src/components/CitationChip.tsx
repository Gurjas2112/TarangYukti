// Citation chips (spec §7.5): issuer · date · valid till; tapping opens the source passage with the verbatim
// quote. Quotes stay in the document's language (never translated).
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Linking, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { expertApi } from "../api/expert";
import { colors, font, radius, space, touch } from "../ui/tokens";

export type CitationCard = {
  marker: string;
  quote: string;
  chunk_id: number | null;
  issuer: string | null;
  title: string | null;
  valid_to: string | null;
};

export function CitationChip({ c, onOpen }: { c: CitationCard; onOpen: (c: CitationCard) => void }) {
  const { t } = useTranslation();
  return (
    <Pressable
      style={styles.chip}
      onPress={() => onOpen(c)}
      accessibilityRole="button"
      accessibilityLabel={`${c.marker} ${c.issuer ?? ""} ${c.title ?? ""}`}
      testID={`citation-${c.marker}`}
    >
      <Text style={styles.chipText}>
        [{c.marker}] {c.issuer ?? "?"}
        {c.valid_to ? ` · ${t("expert.validTill")} ${c.valid_to.slice(0, 10)}` : ""}
      </Text>
    </Pressable>
  );
}

export function CitationDrawer({ c, onClose }: { c: CitationCard | null; onClose: () => void }) {
  const { t } = useTranslation();
  const chunk = useQuery({
    queryKey: ["chunk", c?.chunk_id],
    queryFn: () => expertApi.chunk(c!.chunk_id!),
    enabled: Boolean(c?.chunk_id),
  });
  return (
    <Modal visible={Boolean(c)} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.drawer} testID="citation-drawer">
          <Text style={styles.title} accessibilityRole="header">
            [{c?.marker}] {c?.title ?? c?.issuer}
          </Text>
          <Text style={styles.quote} testID="citation-quote">
            “{c?.quote}”
          </Text>
          {chunk.isLoading ? <ActivityIndicator color={colors.text} /> : null}
          {chunk.data ? (
            <ScrollView style={styles.passage}>
              <Text style={styles.meta}>
                {chunk.data.issuer} · {chunk.data.source_id} · v{chunk.data.version ?? "—"} · {chunk.data.status}
                {chunk.data.valid_to ? ` · ${t("expert.validTill")} ${chunk.data.valid_to.slice(0, 10)}` : ""}
              </Text>
              <Text style={styles.body}>{chunk.data.content}</Text>
              {chunk.data.url ? (
                <Pressable onPress={() => void Linking.openURL(chunk.data!.url!)} accessibilityRole="link">
                  <Text style={styles.link}>{chunk.data.url}</Text>
                </Pressable>
              ) : null}
            </ScrollView>
          ) : null}
          <Pressable style={styles.close} onPress={onClose} accessibilityRole="button" testID="citation-close">
            <Text style={styles.closeText}>{t("why.close")}</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  chip: {
    borderWidth: 1,
    borderColor: colors.action,
    borderRadius: 999,
    paddingHorizontal: space.sm,
    paddingVertical: 2,
    alignSelf: "flex-start",
  },
  chipText: { fontSize: 13, color: colors.action, fontWeight: "600" },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", alignItems: "center", justifyContent: "center", padding: space.lg },
  drawer: { backgroundColor: colors.background, borderRadius: radius.md, padding: space.lg, gap: space.sm, maxWidth: 720, width: "100%", maxHeight: "90%" },
  title: { fontSize: font.body, fontWeight: "700", color: colors.text },
  quote: { fontSize: font.body, color: colors.text, fontStyle: "italic", borderLeftWidth: 4, borderColor: colors.action, paddingLeft: space.sm },
  passage: { maxHeight: 320 },
  meta: { fontSize: 13, color: colors.textMuted, marginBottom: space.xs },
  body: { fontSize: font.small, color: colors.text },
  link: { fontSize: 13, color: colors.link, textDecorationLine: "underline", marginTop: space.xs },
  close: { minHeight: touch.min, backgroundColor: colors.text, borderRadius: radius.sm, alignItems: "center", justifyContent: "center" },
  closeText: { color: colors.background, fontSize: font.body, fontWeight: "700" },
});
