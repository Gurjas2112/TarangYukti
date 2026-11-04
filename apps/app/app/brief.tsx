// Opened by the morning-brief push (url /brief?harbour=…&boat=…&lang=…): shows the card and plays the voice.
// The web service worker keeps this page in Cache Storage so it opens with no signal.
import { Stack, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";

import { BoatKindSchema } from "../src/api/channels";
import { TodayScreen } from "../src/screens/TodayScreen";
import { usePrefs } from "../src/state/prefs";

export default function BriefRoute() {
  const { t } = useTranslation();
  const p = useLocalSearchParams<{ harbour?: string; boat?: string; lang?: string }>();
  const { prefs, lang } = usePrefs();
  const boat = BoatKindSchema.safeParse(p.boat);
  return (
    <>
      <Stack.Screen options={{ headerShown: true, title: t("brief.title") }} />
      <TodayScreen
        harbour={p.harbour ?? prefs.harbour}
        boatKind={boat.success ? boat.data : prefs.boatKind}
        lang={p.lang ?? lang}
        autoplay
      />
    </>
  );
}
