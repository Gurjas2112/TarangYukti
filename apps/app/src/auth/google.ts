// Web: Google sign-in through Supabase OAuth (redirects back to this page).
import { supabase } from "./supabase";

export async function signInWithGoogle(returnPath?: string): Promise<boolean> {
  const { error } = await supabase().auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo:
        typeof window !== "undefined" ? new URL(returnPath ?? window.location.pathname, window.location.origin).href : undefined,
    },
  });
  if (error) throw error;
  return false; // the page navigates away; the session arrives after the redirect
}
