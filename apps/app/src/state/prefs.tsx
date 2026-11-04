// The user's choices on this device: language, harbour, boat type, mode. Kept locally so public use needs no
// login (rule 7); copied to user_prefs when the user signs in.
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import type { BoatKind } from "../api/channels";
import { deviceLanguage, setLanguage } from "../i18n";
import { getItem, setItem } from "../offline/store";

export type Prefs = {
  lang: string | null;
  harbour: string | null;
  boatKind: BoatKind | null;
  mode: "simple" | "expert";
  onboarded: boolean;
  alertsOn: boolean;
};

const KEY = "ty.prefs.v1";
const initial: Prefs = { lang: null, harbour: null, boatKind: null, mode: "simple", onboarded: false, alertsOn: false };

type Ctx = {
  prefs: Prefs;
  loaded: boolean;
  /** The language to render now: the chosen one, else the nearest to the device locale. */
  lang: string;
  update: (p: Partial<Prefs>) => Promise<{ restart: boolean }>;
};

const PrefsContext = createContext<Ctx | null>(null);

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(initial);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    void getItem(KEY).then(async (raw) => {
      const saved = raw ? ({ ...initial, ...JSON.parse(raw) } as Prefs) : initial;
      if (saved.lang) await setLanguage(saved.lang);
      setPrefs(saved);
      setLoaded(true);
    });
  }, []);

  const update = useCallback(
    async (p: Partial<Prefs>) => {
      const next = { ...prefs, ...p };
      setPrefs(next);
      await setItem(KEY, JSON.stringify(next));
      const restart = p.lang ? await setLanguage(p.lang) : false;
      return { restart };
    },
    [prefs],
  );

  const value = useMemo(
    () => ({ prefs, loaded, lang: prefs.lang ?? deviceLanguage() ?? "en-IN", update }),
    [prefs, loaded, update],
  );
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs(): Ctx {
  const c = useContext(PrefsContext);
  if (!c) throw new Error("usePrefs outside PrefsProvider");
  return c;
}
