// Trip tab (Android). Trip mode, the harbour geofence and "I'm back" with the family notice arrive in Milestone 8.
import { useTranslation } from "react-i18next";
import { ScrollView, StyleSheet, Text } from "react-native";

import { useSession } from "../../src/auth/supabase";
import { colors, font, space } from "../../src/ui/tokens";

export default function TripTab() {
  const { t } = useTranslation();
  const { session } = useSession();
  return (
    <ScrollView contentContainerStyle={styles.root} testID="trip-screen">
      <Text style={styles.body}>{session ? t("trip.soon") : t("trip.needsSignIn")}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { padding: space.lg, gap: space.md, backgroundColor: colors.background, flexGrow: 1 },
  body: { fontSize: font.body, color: colors.text },
});
