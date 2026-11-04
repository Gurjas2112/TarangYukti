// Polyfills must be the first imports (spec §17.8).
import "react-native-get-random-values";
import "@copilotkit/react-native/polyfills";
import "react-native-url-polyfill/auto";
import "../src/tasks";
import "../src/i18n";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { router, Stack } from "expo-router";
import { useEffect } from "react";
import { Platform } from "react-native";

import { useSession } from "../src/auth/supabase";
import { CopilotProvider } from "../src/copilot/Provider";
import { registerServiceWorker } from "../src/push/register";
import { PrefsProvider, usePrefs } from "../src/state/prefs";

const queryClient = new QueryClient();

function useOpenFromPush() {
  useEffect(() => {
    if (Platform.OS === "web") {
      void registerServiceWorker(); // offline brief + push (public/sw.js); web only
      return;
    }
    // Android: tapping a push opens its app path (payload carries a path, never coordinates)
    let sub: { remove: () => void } | undefined;
    void import("expo-notifications").then((N) => {
      sub = N.addNotificationResponseReceivedListener((r) => {
        const url = r.notification.request.content.data?.url;
        if (typeof url === "string" && url.startsWith("/")) router.push(url as never);
      });
    });
    return () => sub?.remove();
  }, []);
}

function Shell() {
  const { prefs, lang } = usePrefs();
  const { session } = useSession();
  useOpenFromPush();
  return (
    <CopilotProvider mode={prefs.mode} lang={lang} accessToken={session?.access_token}>
      <Stack screenOptions={{ headerShown: false }} />
    </CopilotProvider>
  );
}

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <PrefsProvider>
        <Shell />
      </PrefsProvider>
    </QueryClientProvider>
  );
}
