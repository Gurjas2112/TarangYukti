// The 23 languages from config/languages.yaml (synced into languages.json by scripts/i18n_draft.py).
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

export function languageInfo(code: string): Language | undefined {
  return allLanguages.find((l) => l.code === code);
}
