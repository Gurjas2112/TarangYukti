// Interface language (spec §6.5): i18next + react-i18next + expo-localization. No language is built in: the
// language is user_prefs.language (chosen at onboarding), else the nearest available language to the device
// locale. Production builds offer only released languages; development, preview and capture builds offer all 23.
import Constants from "expo-constants";
import { getLocales } from "expo-localization";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { I18nManager, Platform } from "react-native";

import { catalogues } from "./catalogues";
import languagesJson from "./languages.json";

export type Language = {
  code: string;
  sarvam_code: string;
  name: string;
  group: "A" | "B";
  script: string;
  rtl: boolean;
  status: "draft" | "released";
};

export const allLanguages = languagesJson as Language[];

function appEnv(): string {
  return (Constants.expoConfig?.extra?.appEnv as string | undefined) ?? "development";
}

/** Languages a user may pick in this build. */
export function availableLanguages(env: string = appEnv()): Language[] {
  if (env === "production") return allLanguages.filter((l) => l.status === "released");
  return allLanguages;
}

export function languageInfo(code: string): Language | undefined {
  return allLanguages.find((l) => l.code === code);
}

export function nearestLanguage(preferred: readonly string[], available: readonly string[]): string | undefined {
  for (const tag of preferred) {
    if (available.includes(tag)) return tag;
    const base = tag.split("-")[0].toLowerCase();
    const match = available.find((a) => a.split("-")[0].toLowerCase() === base);
    if (match) return match;
  }
  return available[0];
}

export function deviceLanguage(): string | undefined {
  const tags = getLocales().map((l) => l.languageTag);
  return nearestLanguage(
    tags,
    availableLanguages().map((l) => l.code),
  );
}

const resources = Object.fromEntries(
  Object.entries(catalogues).map(([code, strings]) => [code, { translation: strings }]),
);

/** English is the fallback for a missing key only (every released catalogue has every key — CI checks). */
const FALLBACK = "en-IN";

// eslint-disable-next-line import/no-named-as-default-member
void i18n.use(initReactI18next).init({
  resources,
  lng: deviceLanguage() ?? FALLBACK,
  fallbackLng: FALLBACK,
  interpolation: { escapeValue: false },
  returnNull: false,
});

/** Switch the interface language. Returns true when the app must restart to flip left/right layout (Android). */
export async function setLanguage(code: string): Promise<boolean> {
  await i18n.changeLanguage(code); // eslint-disable-line import/no-named-as-default-member
  const rtl = languageInfo(code)?.rtl ?? false;
  if (Platform.OS === "web") {
    if (typeof document !== "undefined") {
      document.documentElement.dir = rtl ? "rtl" : "ltr";
      document.documentElement.lang = code;
    }
    return false;
  }
  if (I18nManager.isRTL !== rtl) {
    I18nManager.allowRTL(rtl);
    I18nManager.forceRTL(rtl);
    return true;
  }
  return false;
}

export function t(key: string, opts?: Record<string, unknown>): string {
  return i18n.t(key, opts) as string; // eslint-disable-line import/no-named-as-default-member
}

export { i18n };
