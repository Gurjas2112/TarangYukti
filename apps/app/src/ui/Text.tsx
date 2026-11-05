// Every piece of interface text goes through this component, so it is set in the Noto font of the script of
// the language it is written in (spec §6.5). `lang` overrides the interface language, for example for the
// language names in the picker, each written in its own script.
import { useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";
import { Text as RNText, StyleSheet, type TextProps, type TextStyle } from "react-native";

import { fontFamilyFor, fontsVersion, subscribeFonts } from "./fonts";

function isBold(w: TextStyle["fontWeight"]): boolean {
  if (w === undefined || w === "normal") return false;
  if (w === "bold") return true;
  const n = typeof w === "number" ? w : Number.parseInt(String(w), 10);
  return Number.isFinite(n) && n >= 600;
}

export function Text({ lang, style, ...rest }: TextProps & { lang?: string }) {
  const { i18n } = useTranslation();
  useSyncExternalStore(subscribeFonts, fontsVersion, fontsVersion);
  const flat = (StyleSheet.flatten(style) ?? {}) as TextStyle;
  if (flat.fontFamily) return <RNText style={style} {...rest} />;
  const family = fontFamilyFor(lang ?? i18n.language, isBold(flat.fontWeight));
  if (!family) return <RNText style={style} {...rest} />;
  // The Bold file already is bold: a second synthetic bold would smear on Android.
  return <RNText style={[style, { fontFamily: family, fontWeight: "normal" }]} {...rest} />;
}
