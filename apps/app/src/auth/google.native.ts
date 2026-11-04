// Android: native Google sign-in (one tap) → Supabase signInWithIdToken (spec §9.1.1, §17.3).
import { GoogleSignin, isSuccessResponse } from "@react-native-google-signin/google-signin";

import { getEnv } from "../env";
import { supabase } from "./supabase";

let configured = false;

export async function signInWithGoogle(_returnPath?: string): Promise<boolean> {
  const webClientId = getEnv().GOOGLE_WEB_CLIENT_ID;
  if (!webClientId) throw new Error("Google sign-in is not configured");
  if (!configured) {
    GoogleSignin.configure({ webClientId });
    configured = true;
  }
  await GoogleSignin.hasPlayServices();
  const res = await GoogleSignin.signIn();
  if (!isSuccessResponse(res) || !res.data.idToken) return false;
  const { error } = await supabase().auth.signInWithIdToken({ provider: "google", token: res.data.idToken });
  if (error) throw error;
  return true;
}
