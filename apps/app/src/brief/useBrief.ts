// Today's sea card for (harbour, boat type, language): fetched from channels /brief, saved for offline use,
// and the saved copy shown (marked) when the network is down.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, type BoatKind, type Brief, BriefSchema } from "../api/channels";
import { getItem, setItem } from "../offline/store";

const key = (h: string, b: string, l: string) => `ty.brief.${h}.${b}.${l}`;

export type BriefState = { brief: Brief | null; saved: boolean; loading: boolean; error: boolean; refetch: () => void };

export function useBrief(harbour: string | null, boatKind: BoatKind | null, lang: string): BriefState {
  const enabled = Boolean(harbour && boatKind);
  const q = useQuery({
    queryKey: ["brief", harbour, boatKind, lang],
    queryFn: async () => {
      const b = await api.brief(harbour!, boatKind!, lang);
      await setItem(key(harbour!, boatKind!, lang), JSON.stringify(b));
      return b;
    },
    enabled,
    staleTime: 60_000,
    retry: 1,
  });
  const [offline, setOffline] = useState<Brief | null>(null);
  useEffect(() => {
    if (!enabled || !q.isError) return;
    void getItem(key(harbour!, boatKind!, lang)).then((raw) => {
      const parsed = raw ? BriefSchema.safeParse(JSON.parse(raw)) : null;
      setOffline(parsed?.success ? parsed.data : null);
    });
  }, [enabled, q.isError, harbour, boatKind, lang]);

  const brief = q.data ?? (q.isError ? offline : null);
  return {
    brief,
    saved: !q.data && Boolean(offline),
    loading: q.isLoading,
    error: q.isError,
    refetch: () => void q.refetch(),
  };
}
