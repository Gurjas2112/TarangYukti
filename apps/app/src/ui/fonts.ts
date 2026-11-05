// Noto fonts for every script in use (spec §6.5): bundled with the app, loaded per script with expo-font.
// Only Regular and Bold are bundled. A script's fonts load before the interface switches to a language that
// uses it; until then text falls back to the system font, so nothing ever waits on a font.
import * as Font from "expo-font";
import { Platform } from "react-native";

import { languageInfo } from "../i18n/languages";

type Pair = { regular: string; bold: string; files: () => Record<string, number> };

// Values are functions so a script's files are only required (and on the web, only downloaded) when used.
const SCRIPTS: Record<string, Pair> = {
  Latn: {
    regular: "NotoSans_400Regular",
    bold: "NotoSans_700Bold",
    files: () => ({
      NotoSans_400Regular: require("@expo-google-fonts/noto-sans/400Regular/NotoSans_400Regular.ttf"),
      NotoSans_700Bold: require("@expo-google-fonts/noto-sans/700Bold/NotoSans_700Bold.ttf"),
    }),
  },
  Deva: {
    regular: "NotoSansDevanagari_400Regular",
    bold: "NotoSansDevanagari_700Bold",
    files: () => ({
      NotoSansDevanagari_400Regular: require("@expo-google-fonts/noto-sans-devanagari/400Regular/NotoSansDevanagari_400Regular.ttf"),
      NotoSansDevanagari_700Bold: require("@expo-google-fonts/noto-sans-devanagari/700Bold/NotoSansDevanagari_700Bold.ttf"),
    }),
  },
  Beng: {
    regular: "NotoSansBengali_400Regular",
    bold: "NotoSansBengali_700Bold",
    files: () => ({
      NotoSansBengali_400Regular: require("@expo-google-fonts/noto-sans-bengali/400Regular/NotoSansBengali_400Regular.ttf"),
      NotoSansBengali_700Bold: require("@expo-google-fonts/noto-sans-bengali/700Bold/NotoSansBengali_700Bold.ttf"),
    }),
  },
  Taml: {
    regular: "NotoSansTamil_400Regular",
    bold: "NotoSansTamil_700Bold",
    files: () => ({
      NotoSansTamil_400Regular: require("@expo-google-fonts/noto-sans-tamil/400Regular/NotoSansTamil_400Regular.ttf"),
      NotoSansTamil_700Bold: require("@expo-google-fonts/noto-sans-tamil/700Bold/NotoSansTamil_700Bold.ttf"),
    }),
  },
  Telu: {
    regular: "NotoSansTelugu_400Regular",
    bold: "NotoSansTelugu_700Bold",
    files: () => ({
      NotoSansTelugu_400Regular: require("@expo-google-fonts/noto-sans-telugu/400Regular/NotoSansTelugu_400Regular.ttf"),
      NotoSansTelugu_700Bold: require("@expo-google-fonts/noto-sans-telugu/700Bold/NotoSansTelugu_700Bold.ttf"),
    }),
  },
  Knda: {
    regular: "NotoSansKannada_400Regular",
    bold: "NotoSansKannada_700Bold",
    files: () => ({
      NotoSansKannada_400Regular: require("@expo-google-fonts/noto-sans-kannada/400Regular/NotoSansKannada_400Regular.ttf"),
      NotoSansKannada_700Bold: require("@expo-google-fonts/noto-sans-kannada/700Bold/NotoSansKannada_700Bold.ttf"),
    }),
  },
  Mlym: {
    regular: "NotoSansMalayalam_400Regular",
    bold: "NotoSansMalayalam_700Bold",
    files: () => ({
      NotoSansMalayalam_400Regular: require("@expo-google-fonts/noto-sans-malayalam/400Regular/NotoSansMalayalam_400Regular.ttf"),
      NotoSansMalayalam_700Bold: require("@expo-google-fonts/noto-sans-malayalam/700Bold/NotoSansMalayalam_700Bold.ttf"),
    }),
  },
  Gujr: {
    regular: "NotoSansGujarati_400Regular",
    bold: "NotoSansGujarati_700Bold",
    files: () => ({
      NotoSansGujarati_400Regular: require("@expo-google-fonts/noto-sans-gujarati/400Regular/NotoSansGujarati_400Regular.ttf"),
      NotoSansGujarati_700Bold: require("@expo-google-fonts/noto-sans-gujarati/700Bold/NotoSansGujarati_700Bold.ttf"),
    }),
  },
  Guru: {
    regular: "NotoSansGurmukhi_400Regular",
    bold: "NotoSansGurmukhi_700Bold",
    files: () => ({
      NotoSansGurmukhi_400Regular: require("@expo-google-fonts/noto-sans-gurmukhi/400Regular/NotoSansGurmukhi_400Regular.ttf"),
      NotoSansGurmukhi_700Bold: require("@expo-google-fonts/noto-sans-gurmukhi/700Bold/NotoSansGurmukhi_700Bold.ttf"),
    }),
  },
  Orya: {
    regular: "NotoSansOriya_400Regular",
    bold: "NotoSansOriya_700Bold",
    files: () => ({
      NotoSansOriya_400Regular: require("@expo-google-fonts/noto-sans-oriya/400Regular/NotoSansOriya_400Regular.ttf"),
      NotoSansOriya_700Bold: require("@expo-google-fonts/noto-sans-oriya/700Bold/NotoSansOriya_700Bold.ttf"),
    }),
  },
  Olck: {
    regular: "NotoSansOlChiki_400Regular",
    bold: "NotoSansOlChiki_700Bold",
    files: () => ({
      NotoSansOlChiki_400Regular: require("@expo-google-fonts/noto-sans-ol-chiki/400Regular/NotoSansOlChiki_400Regular.ttf"),
      NotoSansOlChiki_700Bold: require("@expo-google-fonts/noto-sans-ol-chiki/700Bold/NotoSansOlChiki_700Bold.ttf"),
    }),
  },
  Mtei: {
    regular: "NotoSansMeeteiMayek_400Regular",
    bold: "NotoSansMeeteiMayek_700Bold",
    files: () => ({
      NotoSansMeeteiMayek_400Regular: require("@expo-google-fonts/noto-sans-meetei-mayek/400Regular/NotoSansMeeteiMayek_400Regular.ttf"),
      NotoSansMeeteiMayek_700Bold: require("@expo-google-fonts/noto-sans-meetei-mayek/700Bold/NotoSansMeeteiMayek_700Bold.ttf"),
    }),
  },
  // Urdu is written in Nastaliq; Kashmiri and Sindhi in Naskh (their reviewers can change this per language).
  Nastaliq: {
    regular: "NotoNastaliqUrdu_400Regular",
    bold: "NotoNastaliqUrdu_700Bold",
    files: () => ({
      NotoNastaliqUrdu_400Regular: require("@expo-google-fonts/noto-nastaliq-urdu/400Regular/NotoNastaliqUrdu_400Regular.ttf"),
      NotoNastaliqUrdu_700Bold: require("@expo-google-fonts/noto-nastaliq-urdu/700Bold/NotoNastaliqUrdu_700Bold.ttf"),
    }),
  },
  Arab: {
    regular: "NotoNaskhArabic_400Regular",
    bold: "NotoNaskhArabic_700Bold",
    files: () => ({
      NotoNaskhArabic_400Regular: require("@expo-google-fonts/noto-naskh-arabic/400Regular/NotoNaskhArabic_400Regular.ttf"),
      NotoNaskhArabic_700Bold: require("@expo-google-fonts/noto-naskh-arabic/700Bold/NotoNaskhArabic_700Bold.ttf"),
    }),
  },
};

/** The font script key for a language code (Urdu → Nastaliq, other Perso-Arabic → Naskh). */
export function scriptOf(lang: string | undefined): string {
  const info = lang ? languageInfo(lang) : undefined;
  if (!info) return "Latn";
  if (info.script === "Arab") return info.code.startsWith("ur") ? "Nastaliq" : "Arab";
  return SCRIPTS[info.script] ? info.script : "Latn";
}

export const SCRIPT_KEYS = Object.keys(SCRIPTS);

const pending = new Map<string, Promise<void>>();

// Text components subscribe to this so they re-render once a font has loaded.
let version = 0;
const listeners = new Set<() => void>();
export function subscribeFonts(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}
export function fontsVersion(): number {
  return version;
}
function bump(): void {
  version += 1;
  listeners.forEach((cb) => cb());
}

/** Load the Regular and Bold fonts of one script (and Noto Sans for Latin text inside it). Never throws. */
export function loadScript(script: string): Promise<void> {
  const pair = SCRIPTS[script];
  if (!pair) return Promise.resolve();
  let p = pending.get(script);
  if (!p) {
    p = Font.loadAsync(pair.files()).then(bump, () => {
      pending.delete(script); // try again next time; the system font is used meanwhile
    });
    pending.set(script, p);
  }
  return script === "Latn" ? p : Promise.all([p, loadScript("Latn")]).then(() => undefined);
}

export function loadFontsFor(lang: string | undefined): Promise<void> {
  return loadScript(scriptOf(lang));
}

/** Every script, for the language picker (each language name is shown in its own script). */
export function loadAllScripts(): Promise<void> {
  return Promise.all(SCRIPT_KEYS.map(loadScript)).then(() => undefined);
}

/**
 * The fontFamily for text in `lang`, or undefined while its font is not loaded (system font then).
 * On the web a stack lets the browser fall back per character (Latin digits inside Tamil text and so on).
 */
export function fontFamilyFor(lang: string | undefined, bold: boolean): string | undefined {
  const script = scriptOf(lang);
  const pair = SCRIPTS[script];
  const name = bold ? pair.bold : pair.regular;
  if (!Font.isLoaded(name)) return undefined;
  if (Platform.OS !== "web") return name;
  const latin = bold ? SCRIPTS.Latn.bold : SCRIPTS.Latn.regular;
  return script === "Latn" ? `${name}, system-ui, sans-serif` : `${name}, ${latin}, system-ui, sans-serif`;
}
