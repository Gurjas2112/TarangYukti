import { z } from "zod";

// Only EXPO_PUBLIC_* values: they are compiled into the app and public by design. Never a secret here.
const schema = z.object({
  SUPABASE_URL: z.url(),
  SUPABASE_ANON_KEY: z.string().min(1),
  COPILOT_URL: z.url(),
  CHANNELS_URL: z.url(),
  VAPID_PUBLIC_KEY: z.string().optional(),
  GOOGLE_WEB_CLIENT_ID: z.string().optional(),
});

export type PublicEnv = z.infer<typeof schema>;

export function parseEnv(raw: Record<string, string | undefined>): PublicEnv {
  return schema.parse({
    SUPABASE_URL: raw.EXPO_PUBLIC_SUPABASE_URL,
    SUPABASE_ANON_KEY: raw.EXPO_PUBLIC_SUPABASE_ANON_KEY,
    COPILOT_URL: raw.EXPO_PUBLIC_COPILOT_URL,
    CHANNELS_URL: raw.EXPO_PUBLIC_CHANNELS_URL,
    VAPID_PUBLIC_KEY: raw.EXPO_PUBLIC_VAPID_PUBLIC_KEY || undefined,
    GOOGLE_WEB_CLIENT_ID: raw.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID || undefined,
  });
}

let cached: PublicEnv | undefined;

/** Parsed once on first use. Metro inlines EXPO_PUBLIC_* only for literal `process.env.EXPO_PUBLIC_X`. */
export function getEnv(): PublicEnv {
  cached ??= parseEnv({
    EXPO_PUBLIC_SUPABASE_URL: process.env.EXPO_PUBLIC_SUPABASE_URL,
    EXPO_PUBLIC_SUPABASE_ANON_KEY: process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY,
    EXPO_PUBLIC_COPILOT_URL: process.env.EXPO_PUBLIC_COPILOT_URL,
    EXPO_PUBLIC_CHANNELS_URL: process.env.EXPO_PUBLIC_CHANNELS_URL,
    EXPO_PUBLIC_VAPID_PUBLIC_KEY: process.env.EXPO_PUBLIC_VAPID_PUBLIC_KEY,
    EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
  });
  return cached;
}
