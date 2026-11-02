// Minimal catalogue lookup for Milestone 1. Milestone 6 replaces this with i18next + react-i18next.
// No language is built in: the language is user_prefs.language, else the nearest available catalogue
// to the device locale.
import { getLocales } from "expo-localization";

import enIN from "./en-IN.json";

type Catalogue = Record<string, string>;

export const catalogues: Record<string, Catalogue> = { "en-IN": enIN };

export function nearestLanguage(preferred: readonly string[], available: readonly string[]): string {
  for (const tag of preferred) {
    if (available.includes(tag)) return tag;
    const base = tag.split("-")[0];
    const match = available.find((a) => a.split("-")[0] === base);
    if (match) return match;
  }
  // TODO(tarangyukti): Milestone 10a — only released languages count; the onboarding picker decides.
  return available[0];
}

export function deviceLanguage(): string {
  const tags = getLocales().map((l) => l.languageTag);
  return nearestLanguage(tags, Object.keys(catalogues));
}

export function t(key: string, lang: string = deviceLanguage()): string {
  return catalogues[lang]?.[key] ?? key;
}
