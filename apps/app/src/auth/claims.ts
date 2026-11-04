// Role and MFA level from the Supabase access token (custom access token hook adds `app_role`). Display and route
// gating only: every server and database check verifies the token itself (spec §9.1).
export type AppRole = "fisher" | "family" | "analyst" | "officer" | "platform_admin";

export function decodeClaims(token: string | null | undefined): Record<string, unknown> | null {
  if (!token) return null;
  const part = token.split(".")[1];
  if (!part) return null;
  try {
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (part.length % 4)) % 4);
    return JSON.parse(atob(b64)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function roleOf(token: string | null | undefined): AppRole | null {
  const r = decodeClaims(token)?.app_role;
  return typeof r === "string" ? (r as AppRole) : null;
}

export function aalOf(token: string | null | undefined): "aal1" | "aal2" | null {
  const a = decodeClaims(token)?.aal;
  return a === "aal1" || a === "aal2" ? a : null;
}

export const STAFF: AppRole[] = ["analyst", "officer", "platform_admin"];
