import { useQuery } from "@tanstack/react-query";
import { Redirect, Tabs } from "expo-router";
import { useTranslation } from "react-i18next";
import { Platform } from "react-native";
import { Text } from "../../src/ui/Text";

import { api } from "../../src/api/channels";
import { useSession } from "../../src/auth/supabase";
import { LanguageButton } from "../../src/components/LanguagePicker";
import { LiveTracking } from "../../src/location/useLiveTracking";
import { usePrefs } from "../../src/state/prefs";
import { colors, font } from "../../src/ui/tokens";

const icon = (s: string) =>
  function TabIcon() {
    return <Text style={{ fontSize: font.body }}>{s}</Text>;
  };

/** Simple tabs (spec §17.9): Today · Map · Trip (Android) · Alerts · Me. The language button is on every screen. */
export default function SimpleLayout() {
  const { t } = useTranslation();
  const { prefs, loaded } = usePrefs();
  const { session } = useSession();
  const token = session?.access_token;
  const me = useQuery({
    queryKey: ["me", session?.user.id],
    queryFn: () => api.me(token!),
    enabled: Boolean(token),
  });
  if (loaded && !prefs.onboarded) return <Redirect href="/onboarding" />;
  return (
    <LiveTracking boatId={me.data?.boats[0]?.id ?? null}>
      <Tabs
        screenOptions={{
          headerRight: () => <LanguageButton />,
          headerTitleStyle: { fontSize: font.body + 2, color: colors.text },
          tabBarActiveTintColor: colors.text,
          tabBarInactiveTintColor: colors.textMuted,
          tabBarLabelStyle: { fontSize: font.small - 2, fontWeight: "700" },
          tabBarStyle: { minHeight: 64 },
        }}
      >
        <Tabs.Screen
          name="index"
          options={{
            title: t("tabs.today"),
            tabBarIcon: icon("🌊"),
            tabBarButtonTestID: "tab-today",
          }}
        />
        <Tabs.Screen
          name="map"
          options={{
            title: t("tabs.map"),
            tabBarIcon: icon("🗺"),
            tabBarButtonTestID: "tab-map",
          }}
        />
        <Tabs.Screen
          name="trip"
          options={{
            title: t("tabs.trip"),
            tabBarIcon: icon("⛵"),
            tabBarButtonTestID: "tab-trip",
            href: Platform.OS === "web" ? null : undefined,
          }}
        />
        <Tabs.Screen
          name="alerts"
          options={{
            title: t("tabs.alerts"),
            tabBarIcon: icon("🔔"),
            tabBarButtonTestID: "tab-alerts",
          }}
        />
        <Tabs.Screen
          name="me"
          options={{
            title: t("tabs.me"),
            tabBarIcon: icon("👤"),
            tabBarButtonTestID: "tab-me",
          }}
        />
      </Tabs>
    </LiveTracking>
  );
}
