import { TodayScreen } from "../../src/screens/TodayScreen";
import { usePrefs } from "../../src/state/prefs";

export default function Today() {
  const { prefs, lang } = usePrefs();
  return <TodayScreen harbour={prefs.harbour} boatKind={prefs.boatKind} lang={lang} />;
}
