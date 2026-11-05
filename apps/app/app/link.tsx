// "Add this phone" deep link: tarangyukti://link?token_hash=…&type=magiclink (from the QR on the Me tab).
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { StyleSheet, View } from "react-native";
import { Text } from "../src/ui/Text";

import { verifyPhoneLink } from "../src/auth/supabase";
import { colors, font, space } from "../src/ui/tokens";

export default function Link() {
  const { t } = useTranslation();
  const { token_hash } = useLocalSearchParams<{ token_hash?: string }>();
  const [state, setState] = useState<"working" | "done" | "failed">(token_hash ? "working" : "failed");
  useEffect(() => {
    if (!token_hash) return;
    verifyPhoneLink(token_hash)
      .then(() => {
        setState("done");
        setTimeout(() => router.replace("/"), 1200);
      })
      .catch(() => setState("failed"));
  }, [token_hash]);
  return (
    <View style={styles.root} testID="link-screen">
      <Text style={styles.body}>
        {state === "working" ? t("link.title") : state === "done" ? t("link.done") : t("link.failed")}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, padding: space.lg, justifyContent: "center", backgroundColor: colors.background },
  body: { fontSize: font.title, color: colors.text, textAlign: "center" },
});
