// Polyfills must be the first imports (spec §17.8).
import "react-native-get-random-values";
import "@copilotkit/react-native/polyfills";
import "react-native-url-polyfill/auto";
import "../src/tasks";

import { Stack } from "expo-router";

import { CopilotProvider } from "../src/copilot/Provider";
import { deviceLanguage } from "../src/i18n";

export default function RootLayout() {
  // TODO(tarangyukti): Milestone 9 — session from Supabase auth; mode/lang from user_prefs.
  return (
    <CopilotProvider mode="simple" lang={deviceLanguage()}>
      <Stack screenOptions={{ headerShown: false }} />
    </CopilotProvider>
  );
}
