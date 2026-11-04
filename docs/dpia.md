# Data protection impact assessment (draft)

DPDP Act 2023 and DPDP Rules 2025 (spec §9.4). **Draft for the prototype — to be completed, reviewed and signed by
the privacy officer before any real user is invited (Gate LT).** Not legal advice.

## What is processed and why

| Data | Purpose (consent) | Where | Kept |
|---|---|---|---|
| Google account e-mail, user id | Sign-in; family sharing by e-mail | Supabase Auth (Mumbai) | Until the account is deleted (7-day undo) |
| Language, harbour, boat type, quiet hours | Advice in the user's language for their boat | Supabase `user_prefs`, `boats` | Until deleted |
| Live positions (while trip mode / app open) | Border and park alerts; trips; family notice (`location_alerts`) | Supabase `positions` (RLS) | 30 days, then H3 cell counts with no user id |
| Trips, feedback 👍/👎 | "I'm back", family notice, advice quality | Supabase `trips` | Until deleted |
| Voice notes | Speech-to-text to answer (`voice_processing`) | Sent to Sarvam AI; **not stored** | Not stored |
| Questions and replies | Answering; audit of AI advice | Gemini (outside India) for the answer; Supabase `answers` | 180 days |
| Push tokens | Alerts and briefs | Supabase `push_subscriptions` | Until revoked or invalid |
| Consents | Proof of consent per purpose and notice version | Supabase `consents`, audit log | ≥ 1 year |

Never sent to the LLM, caches, the ledger graph, logs or traces: names, phone numbers, e-mail addresses or raw
coordinates (H3 cells only; span exporter scrubs tokens, e-mails and coordinate pairs).

## Rights (Me → My data, Me → Help)

- Access: download everything as JSON (`/me/export`).
- Erasure: delete the account; 7-day undo; completed by the nightly job, well within 90 days.
- Correction: harbour, boat and language in Me; anything else through the grievance officer.
- Withdraw consent: turn alerts off / delete the account; logged in `consents` and `audit_log`.

## Risks and controls

| Risk | Control | Residual |
|---|---|---|
| Another user or a family member sees positions | RLS on every table; cross-user tests (`make test-rls`); grants expire ≤ 90 days | Low |
| Staff misuse | Roles via JWT claim; MFA (aal2); officers see positions only inside active warnings, last hour; admin actions audit-logged in a hash chain | Low |
| Gemini processes questions outside India | No personal identifiers or coordinates in prompts; disclosed in the notice | Medium — accepted for the prototype; review before live |
| Unsafe advice | Deterministic constraints decide; official warnings force NO-GO; "Advisory only"; approved phrases only | Medium — mitigated by human review of phrases and the failures dataset |
| Breach | Breach runbook (`docs/incident-runbook.md`); CERT-In 6 h; DPDP Board notification | — |
| Children | Adults only at sign-up | Low |

## Sign-off

| Role | Name | Date |
|---|---|---|
| Privacy officer | _to be appointed_ | |
| Safety owner | | |
