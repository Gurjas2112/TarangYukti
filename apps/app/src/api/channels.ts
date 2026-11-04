// Typed client for ty-channels (spec §6.8, §9.1.3). Every response is checked with Zod.
import { z } from "zod";

import { getEnv } from "../env";

export const VerdictSchema = z.enum(["GO", "CAUTION", "NO-GO"]);
export type Verdict = z.infer<typeof VerdictSchema>;

export const BriefSchema = z.object({
  harbour: z.object({ id: z.string(), name: z.string() }),
  boat_type: z.string(),
  lang: z.string(),
  as_of: z.string().nullable(),
  verdict: VerdictSchema,
  headline: z.string(),
  why: z.array(z.string()),
  window: z.object({ depart: z.string(), back_by: z.string(), verdict: VerdictSchema }).nullable(),
  ribbon: z.array(z.object({ time: z.string(), verdict: VerdictSchema })),
  spot: z.object({ distance_km: z.number(), text: z.string() }).nullable(),
  border: z.object({ distance_km: z.number(), text: z.string() }),
  stale: z.string().nullable(),
  footer: z.string(),
  answer_id: z.string().nullable().optional(),
  simulation: z.boolean(),
  sources: z.array(z.string()),
  fetched_at: z.string(),
  speak: z.string(),
});
export type Brief = z.infer<typeof BriefSchema>;

export const HarbourSchema = z.object({
  id: z.string(),
  name: z.string(),
  state: z.string(),
  lat: z.number(),
  lon: z.number(),
  suggested_language: z.string().nullable(),
});
export type Harbour = z.infer<typeof HarbourSchema>;

export const BoatKindSchema = z.enum(["non_motorised", "small_frp", "mechanised_trawler"]);
export type BoatKind = z.infer<typeof BoatKindSchema>;

const MeSchema = z.object({
  prefs: z
    .object({
      mode: z.enum(["simple", "expert"]),
      language: z.string().nullable(),
      home_harbour: z.string().nullable(),
      brief_time: z.string().nullable(),
      quiet_from: z.string(),
      quiet_to: z.string(),
    })
    .nullable(),
  role: z.string().nullable(),
  boats: z.array(z.object({ id: z.string(), name: z.string(), kind: BoatKindSchema, home_harbour: z.string().nullable() })),
  consents: z.array(
    z.object({ purpose: z.string(), notice_version: z.string(), language: z.string(), given_at: z.string() }),
  ),
  push: z.array(z.object({ kind: z.enum(["web", "expo"]) })),
});
export type Me = z.infer<typeof MeSchema>;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, schema: z.ZodType<T>, init: RequestInit & { token?: string | null } = {}): Promise<T> {
  const { token, headers, ...rest } = init;
  const res = await fetch(`${getEnv().CHANNELS_URL}${path}`, {
    ...rest,
    headers: {
      ...(rest.body && !(rest.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}) as { detail?: string });
    throw new ApiError(res.status, (detail as { detail?: string }).detail ?? res.statusText);
  }
  return schema.parse(await res.json());
}

export const api = {
  brief: (harbour: string, boatType: BoatKind, lang: string) =>
    call(`/brief?${new URLSearchParams({ harbour, boat_type: boatType, lang })}`, BriefSchema),
  harbours: () => call("/harbours", z.object({ harbours: z.array(HarbourSchema) })).then((r) => r.harbours),
  consent: (lang: string) =>
    call(
      `/consent?${new URLSearchParams({ lang })}`,
      z.object({ notice_version: z.string(), short: z.string(), agree: z.string(), lang: z.string() }),
    ),
  tts: (text: string, lang: string) =>
    call("/tts", z.object({ url: z.string().nullable() }), { method: "POST", body: JSON.stringify({ text, lang }) }),
  stt: (form: FormData, token?: string | null) =>
    call("/stt", z.object({ text: z.string(), lang: z.string() }), { method: "POST", body: form, token }),
  me: (token: string) => call("/me", MeSchema, { token }),
  onboarding: (
    token: string,
    body: { language: string; harbour: string; boat_kind: BoatKind; consents: string[]; notice_version: string },
  ) => call("/onboarding", z.object({ boat_id: z.string() }), { method: "POST", body: JSON.stringify(body), token }),
  prefs: (token: string, body: Partial<{ mode: string; language: string; home_harbour: string }>) =>
    call("/me/prefs", z.object({ status: z.string() }), { method: "PUT", body: JSON.stringify(body), token }),
  subscribe: (
    token: string,
    body: { kind: "web" | "expo"; endpoint: string; p256dh?: string; auth?: string; user_agent?: string },
  ) => call("/push/subscribe", z.object({ status: z.string() }), { method: "POST", body: JSON.stringify(body), token }),
  phoneLink: (token: string) =>
    call("/phone-link", z.object({ token_hash: z.string(), type: z.string(), expires_in: z.number(), qr: z.string() }), {
      method: "POST",
      token,
    }),
};
