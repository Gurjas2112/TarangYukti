// Supabase client (publishable key only). Sessions persist in AsyncStorage on Android and localStorage on web.
import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { Platform } from "react-native";

import { getEnv } from "../env";

let client: ReturnType<typeof createClient> | undefined;

export function supabase() {
  client ??= createClient(getEnv().SUPABASE_URL, getEnv().SUPABASE_ANON_KEY, {
    auth: {
      storage: Platform.OS === "web" ? undefined : AsyncStorage,
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: Platform.OS === "web",
    },
  });
  return client;
}

export function useSession(): { session: Session | null; ready: boolean } {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let alive = true;
    void supabase()
      .auth.getSession()
      .then(({ data }) => {
        if (alive) {
          setSession(data.session);
          setReady(true);
        }
      });
    const { data } = supabase().auth.onAuthStateChange((_e, s) => setSession(s));
    return () => {
      alive = false;
      data.subscription.unsubscribe();
    };
  }, []);
  return { session, ready };
}

/** "Add this phone": sign in with the one-time token from the QR (10-minute expiry, spec §9.1.3). */
export async function verifyPhoneLink(tokenHash: string): Promise<void> {
  const { error } = await supabase().auth.verifyOtp({ token_hash: tokenHash, type: "magiclink" });
  if (error) throw error;
}

export async function signOut(): Promise<void> {
  await supabase().auth.signOut();
}
