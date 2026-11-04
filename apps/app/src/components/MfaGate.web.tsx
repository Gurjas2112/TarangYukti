// Staff screens need TOTP (aal2) — spec §9.1: enrol once with an authenticator app, then enter a code each session.
import QRCode from "react-native-qrcode-svg";
import { type ReactNode, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { aalOf, type AppRole, roleOf } from "../auth/claims";
import { signInWithGoogle } from "../auth/google";
import { supabase, useSession } from "../auth/supabase";
import { colors } from "../ui/tokens";

type Factor = { id: string; status: string };
const box: React.CSSProperties = { maxWidth: 480, margin: "64px auto", padding: 24, border: `1px solid ${colors.border}`, borderRadius: 12, background: "#fff", fontSize: 16 };

export function MfaGate({ roles, children }: { roles: AppRole[]; children: ReactNode }) {
  const { t } = useTranslation();
  const { session, ready } = useSession();
  const token = session?.access_token;
  const [factors, setFactors] = useState<Factor[] | null>(null);
  const [enrol, setEnrol] = useState<{ id: string; uri: string; secret: string } | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    void supabase()
      .auth.mfa.listFactors()
      .then(({ data }) => setFactors((data?.totp ?? []) as Factor[]));
  }, [token]);

  if (!ready) return null;
  if (!token) {
    return (
      <div style={box} data-testid="staff-sign-in">
        <p>{t("staff.signIn")}</p>
        <button onClick={() => void signInWithGoogle(window.location.pathname)}>{t("me.signIn")}</button>
      </div>
    );
  }
  const role = roleOf(token);
  if (!role || !roles.includes(role)) {
    return (
      <div style={box} data-testid="staff-forbidden">
        <p>{t("staff.notAllowed")}</p>
        <p style={{ color: colors.textMuted, fontSize: 13 }}>{t("staff.roleNow", { role: role ?? "—" })}</p>
      </div>
    );
  }
  if (aalOf(token) === "aal2") return <>{children}</>;

  async function startEnrol() {
    setError(null);
    const { data, error: e } = await supabase().auth.mfa.enroll({ factorType: "totp", friendlyName: "TarangYukti staff" });
    if (e || !data) return setError(t("staff.mfaFailed"));
    setEnrol({ id: data.id, uri: data.totp.uri, secret: data.totp.secret });
  }

  async function verify(factorId: string) {
    setError(null);
    const { data: ch, error: e1 } = await supabase().auth.mfa.challenge({ factorId });
    if (e1 || !ch) return setError(t("staff.mfaFailed"));
    const { error: e2 } = await supabase().auth.mfa.verify({ factorId, challengeId: ch.id, code: code.trim() });
    if (e2) return setError(t("staff.codeWrong"));
    await supabase().auth.refreshSession(); // the new token carries aal2
  }

  const verified = (factors ?? []).find((f) => f.status === "verified");
  return (
    <div style={box} data-testid="mfa-gate">
      <h2 style={{ marginTop: 0 }}>{t("staff.mfaTitle")}</h2>
      {verified || enrol ? (
        <>
          {enrol ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
              <p>{t("staff.scan")}</p>
              <QRCode value={enrol.uri} size={180} />
              <code style={{ fontSize: 12 }}>{enrol.secret}</code>
            </div>
          ) : (
            <p>{t("staff.enterCode")}</p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void verify(enrol?.id ?? verified!.id);
            }}
            style={{ display: "flex", gap: 8, marginTop: 12 }}
          >
            <input
              data-testid="mfa-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              aria-label={t("staff.code")}
              style={{ fontSize: 20, letterSpacing: 4, width: 140 }}
            />
            <button type="submit" data-testid="mfa-verify">
              {t("staff.verify")}
            </button>
          </form>
        </>
      ) : (
        <button onClick={() => void startEnrol()} data-testid="mfa-enrol">
          {t("staff.enrol")}
        </button>
      )}
      {error ? <p style={{ color: colors.noGo }}>{error}</p> : null}
    </div>
  );
}
