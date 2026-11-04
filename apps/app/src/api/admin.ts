// Admin console API (channels /admin/*, platform_admin + MFA). Zod-checked; rows are loose records because the
// console shows them as tables.
import { z } from "zod";

import { getEnv } from "../env";

const Row = z.record(z.string(), z.unknown());
export type AdminRow = z.infer<typeof Row>;

async function req<T>(token: string, path: string, schema: z.ZodType<T>, init: RequestInit = {}): Promise<T> {
  const r = await fetch(`${getEnv().CHANNELS_URL}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...(init.body ? { "Content-Type": "application/json" } : {}) },
  });
  if (!r.ok) {
    const d = (await r.json().catch(() => ({}))) as { detail?: unknown };
    throw new Error(typeof d.detail === "string" ? d.detail : `${r.status}`);
  }
  return schema.parse(await r.json());
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const adminApi = {
  overview: (t: string) => req(t, "/admin/overview", Row),
  sources: (t: string) => req(t, "/admin/sources", z.object({ sources: z.array(Row) })).then((r) => r.sources),
  kb: (t: string) => req(t, "/admin/kb", z.object({ documents: z.array(Row) })).then((r) => r.documents),
  kbDecide: (t: string, id: string, approve: boolean, reason: string) =>
    req(t, `/admin/kb/${id}/decide`, Row, post({ approve, reason })),
  kbSupersede: (t: string, id: string, by: string, reason: string) =>
    req(t, `/admin/kb/${id}/supersede`, Row, post({ by, reason })),
  alerts: (t: string) => req(t, "/admin/alerts", z.object({ alerts: z.array(Row) })).then((r) => r.alerts),
  retry: (t: string, id: string) => req(t, `/admin/alerts/${id}/retry`, Row, { method: "POST" }),
  guardrails: (t: string) => req(t, "/admin/guardrails", z.object({ answers: z.array(Row) })).then((r) => r.answers),
  addFailure: (t: string, answerId: string | null, wrong: string, expect?: string) =>
    req(t, "/admin/failures", Row, post({ answer_id: answerId, wrong, ...(expect ? { expect } : {}) })),
  replay: (t: string, id: string) => req(t, `/admin/replay/${id}`, z.object({ answer: Row, ledger: Row.nullable() })),
  users: (t: string) => req(t, "/admin/users", z.object({ users: z.array(Row) })).then((r) => r.users),
  setRole: (t: string, id: string, role: string, reason: string) => req(t, `/admin/users/${id}/role`, Row, post({ role, reason })),
  invite: (t: string, email: string, role: string, reason: string) => req(t, "/admin/invite", Row, post({ email, role, reason })),
  live: (t: string) => req(t, "/admin/live", z.object({ cells: z.array(Row) })).then((r) => r.cells),
  audit: (t: string) => req(t, "/admin/audit", z.object({ events: z.array(Row) })).then((r) => r.events),
  verify: (t: string) => req(t, "/admin/audit/verify", z.object({ intact: z.boolean(), first_broken_id: z.number().nullable() }), { method: "POST" }),
  setFlag: (t: string, key: "free_chat_off" | "alerts_paused", value: boolean | string[], reason: string) =>
    req(t, `/admin/flags/${key}`, Row, post({ value, reason })),
};
