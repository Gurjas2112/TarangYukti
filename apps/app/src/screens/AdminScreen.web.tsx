// Admin console (spec §10.3): platform_admin with MFA. Every action asks for a reason and is audit-logged in the
// database. Personal data is minimised: alerts and audit events show pseudonymous references; the live map shows
// coarse cell counts only.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { type AdminRow, adminApi } from "../api/admin";
import { useSession } from "../auth/supabase";
import { colors } from "../ui/tokens";

const TABS = ["overview", "sources", "kb", "alerts", "guardrails", "replay", "users", "live", "audit", "switches"] as const;
type Tab = (typeof TABS)[number];

const cell: React.CSSProperties = { padding: "4px 8px", borderTop: "1px solid #eee", verticalAlign: "top", fontSize: 13 };
const btn: React.CSSProperties = { marginRight: 6 };

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function Table({ rows, cols, actions }: { rows: AdminRow[]; cols: string[]; actions?: (r: AdminRow) => React.ReactNode }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          {cols.map((c) => (
            <th key={c} style={{ ...cell, textAlign: "left", background: colors.foam }}>
              {c}
            </th>
          ))}
          {actions ? <th style={cell} /> : null}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={String(r.id ?? i)}>
            {cols.map((c) => (
              <td key={c} style={{ ...cell, maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis" }}>
                {fmt(r[c])}
              </td>
            ))}
            {actions ? <td style={cell}>{actions(r)}</td> : null}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ask(label: string): string | null {
  const r = window.prompt(label);
  return r && r.trim().length >= 3 ? r.trim() : null;
}

export function AdminScreen() {
  const { t } = useTranslation();
  const { session } = useSession();
  const token = session!.access_token;
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [replayId, setReplayId] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const q = <T,>(key: string, fn: () => Promise<T>, on: boolean) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useQuery({ queryKey: ["admin", key], queryFn: fn, enabled: on });
  const overview = q("overview", () => adminApi.overview(token), tab === "overview" || tab === "switches");
  const sources = q("sources", () => adminApi.sources(token), tab === "sources");
  const kb = q("kb", () => adminApi.kb(token), tab === "kb");
  const alerts = q("alerts", () => adminApi.alerts(token), tab === "alerts");
  const guard = q("guard", () => adminApi.guardrails(token), tab === "guardrails");
  const users = q("users", () => adminApi.users(token), tab === "users");
  const live = q("live", () => adminApi.live(token), tab === "live");
  const audit = q("audit", () => adminApi.audit(token), tab === "audit");
  const replay = useQuery({
    queryKey: ["admin", "replay", replayId],
    queryFn: () => adminApi.replay(token, replayId),
    enabled: tab === "replay" && replayId.length >= 36,
    retry: false,
  });

  async function act(fn: () => Promise<unknown>, done: string, refresh: string) {
    try {
      await fn();
      setNote(done);
      await qc.invalidateQueries({ queryKey: ["admin", refresh] });
    } catch (e) {
      setNote(`${t("admin.failed")}: ${(e as Error).message}`);
    }
  }

  const o = overview.data ?? {};
  const flags = (o.flags ?? {}) as { free_chat_off?: boolean; alerts_paused?: string[] };
  return (
    <div style={{ position: "fixed", inset: 0, display: "flex", flexDirection: "column", background: colors.foam, fontFamily: "system-ui, 'Noto Sans', sans-serif" }}>
      <header style={{ background: colors.deep, color: "#fff", padding: "8px 16px", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <strong style={{ marginRight: 12 }}>{t("admin.title")}</strong>
        {TABS.map((x) => (
          <button key={x} data-testid={`admin-tab-${x}`} onClick={() => setTab(x)} style={{ fontWeight: tab === x ? 800 : 400 }}>
            {t(`admin.tabs.${x}`)}
          </button>
        ))}
      </header>
      {note ? (
        <p data-testid="admin-note" style={{ margin: 0, padding: "6px 16px", background: "#fff8e1" }}>
          {note}
        </p>
      ) : null}
      <main style={{ flex: 1, overflow: "auto", padding: 16 }} data-testid={`admin-${tab}`}>
        {tab === "overview" ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
            {Object.entries(o)
              .filter(([k]) => k !== "flags")
              .map(([k, v]) => (
                <div key={k} style={{ background: "#fff", border: "1px solid #ddd", borderRadius: 8, padding: 12 }} data-testid={`metric-${k}`}>
                  <div style={{ fontSize: 13, color: colors.textMuted }}>{t(`admin.metric.${k}`, { defaultValue: k })}</div>
                  <div style={{ fontSize: 26, fontWeight: 800 }}>{fmt(v)}</div>
                </div>
              ))}
          </div>
        ) : null}

        {tab === "sources" && sources.data ? <Table rows={sources.data} cols={["tool", "source", "available", "cache", "confidence", "fetched_at", "notes"]} /> : null}

        {tab === "kb" && kb.data ? (
          <Table
            rows={kb.data}
            cols={["issuer", "source_id", "version", "doc_type", "status", "valid_to", "chunks", "superseded_at"]}
            actions={(r) =>
              r.status === "quarantined" ? (
                <>
                  <button style={btn} onClick={() => { const why = ask(t("admin.reason")); if (why) void act(() => adminApi.kbDecide(token, String(r.id), true, why), t("admin.done"), "kb"); }}>
                    {t("admin.approve")}
                  </button>
                  <button onClick={() => { const why = ask(t("admin.reason")); if (why) void act(() => adminApi.kbDecide(token, String(r.id), false, why), t("admin.done"), "kb"); }}>
                    {t("admin.reject")}
                  </button>
                </>
              ) : r.status === "active" ? (
                <button
                  onClick={() => {
                    const by = window.prompt(t("admin.supersedeBy"));
                    const why = by ? ask(t("admin.reason")) : null;
                    if (by && why) void act(() => adminApi.kbSupersede(token, String(r.id), by.trim(), why), t("admin.done"), "kb");
                  }}
                >
                  {t("admin.supersede")}
                </button>
              ) : null
            }
          />
        ) : null}

        {tab === "alerts" && alerts.data ? (
          <Table
            rows={alerts.data}
            cols={["created_at", "kind", "rule", "critical", "status", "attempts", "lang", "title", "user_ref"]}
            actions={(r) =>
              r.status === "failed" ? (
                <button onClick={() => void act(() => adminApi.retry(token, String(r.id)), t("admin.done"), "alerts")}>{t("admin.retry")}</button>
              ) : null
            }
          />
        ) : null}

        {tab === "guardrails" && guard.data ? (
          <Table
            rows={guard.data}
            cols={["created_at", "lang", "mode", "question", "reply", "guard", "fallback", "prompt_version"]}
            actions={(r) => (
              <button
                data-testid="add-failure"
                onClick={() => {
                  const wrong = ask(t("admin.whatWasWrong"));
                  if (wrong) void act(() => adminApi.addFailure(token, String(r.id), wrong), t("admin.failureAdded"), "guard");
                }}
              >
                {t("admin.addFailure")}
              </button>
            )}
          />
        ) : null}

        {tab === "replay" ? (
          <div>
            <input
              data-testid="replay-id"
              value={replayId}
              onChange={(e) => setReplayId(e.target.value.trim())}
              placeholder={t("admin.replayId")}
              style={{ width: 380, fontSize: 15, padding: 6 }}
            />
            {replay.isError ? <p>{t("admin.notFound")}</p> : null}
            {replay.data ? (
              <div data-testid="replay-result">
                <h3>{fmt(replay.data.answer.verdict)} · {fmt(replay.data.answer.created_at)}</h3>
                <p style={{ whiteSpace: "pre-wrap" }}>{fmt(replay.data.answer.reply)}</p>
                <p style={{ fontSize: 13, color: colors.textMuted }}>
                  model {fmt(replay.data.answer.model)} · prompt {fmt(replay.data.answer.prompt_version)} · config {fmt(replay.data.answer.config_version)}
                </p>
                {replay.data.ledger ? (
                  <Table
                    rows={((replay.data.ledger.results as AdminRow[]) ?? []).map((x) => ({
                      ...x,
                      observations: ((x.observations as AdminRow[]) ?? []).map((ob) => `${fmt(ob.var)}=${fmt(ob.value)} valid ${fmt(ob.valid_at)} known ${fmt(ob.known_at)} (${fmt(ob.dataset)})`).join("; "),
                    }))}
                    cols={["id", "ok", "value", "unit", "detail", "unknown", "observations"]}
                  />
                ) : null}
                <button onClick={() => window.print()}>{t("admin.exportPdf")}</button>
              </div>
            ) : null}
          </div>
        ) : null}

        {tab === "users" && users.data ? (
          <>
            <button
              style={{ marginBottom: 8 }}
              data-testid="invite-staff"
              onClick={() => {
                const email = window.prompt(t("admin.inviteEmail"));
                const role = email ? window.prompt(t("admin.inviteRole"), "analyst") : null;
                const why = role ? ask(t("admin.reason")) : null;
                if (email && role && why) void act(() => adminApi.invite(token, email, role, why), t("admin.done"), "users");
              }}
            >
              {t("admin.invite")}
            </button>
            <Table
              rows={users.data}
              cols={["email", "role", "mfa", "deleting", "created_at", "last_sign_in_at"]}
              actions={(r) => (
                <button
                  onClick={() => {
                    const role = window.prompt(t("admin.newRole"), String(r.role));
                    const why = role ? ask(t("admin.reason")) : null;
                    if (role && why) void act(() => adminApi.setRole(token, String(r.id), role, why), t("admin.done"), "users");
                  }}
                >
                  {t("admin.changeRole")}
                </button>
              )}
            />
          </>
        ) : null}

        {tab === "live" && live.data ? (
          <>
            <p style={{ fontSize: 13, color: colors.textMuted }}>{t("admin.liveNote")}</p>
            <Table rows={live.data} cols={["lat", "lon", "boats"]} />
          </>
        ) : null}

        {tab === "audit" && audit.data ? (
          <>
            <button
              data-testid="audit-verify"
              style={{ marginBottom: 8 }}
              onClick={() =>
                void adminApi
                  .verify(token)
                  .then((r) => setNote(r.intact ? t("admin.chainIntact") : t("admin.chainBroken", { id: r.first_broken_id })))
              }
            >
              {t("admin.verifyChain")}
            </button>
            <Table rows={audit.data} cols={["id", "at", "action", "target", "detail", "actor_ref"]} />
          </>
        ) : null}

        {tab === "switches" ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 640 }}>
            <label style={{ fontSize: 16 }}>
              <input
                type="checkbox"
                data-testid="switch-free-chat"
                checked={Boolean(flags.free_chat_off)}
                onChange={(e) => {
                  const why = ask(t("admin.reason"));
                  if (why) void act(() => adminApi.setFlag(token, "free_chat_off", e.target.checked, why), t("admin.done"), "overview");
                }}
              />{" "}
              {t("admin.freeChatOff")}
            </label>
            <p style={{ fontSize: 13, color: colors.textMuted, margin: 0 }}>{t("admin.freeChatHelp")}</p>
            <label style={{ fontSize: 16 }}>
              {t("admin.alertsPaused")}:{" "}
              <code data-testid="paused-regions">{(flags.alerts_paused ?? []).join(", ") || "—"}</code>{" "}
              <button
                onClick={() => {
                  const ids = window.prompt(t("admin.pausedPrompt"), (flags.alerts_paused ?? []).join(","));
                  const why = ids !== null ? ask(t("admin.reason")) : null;
                  if (ids !== null && why) {
                    const list = ids.split(",").map((x) => x.trim()).filter(Boolean);
                    void act(() => adminApi.setFlag(token, "alerts_paused", list, why), t("admin.done"), "overview");
                  }
                }}
              >
                {t("admin.change")}
              </button>
            </label>
            <p style={{ fontSize: 13, color: colors.textMuted, margin: 0 }}>{t("admin.alertsPausedHelp")}</p>
          </div>
        ) : null}
      </main>
    </div>
  );
}
