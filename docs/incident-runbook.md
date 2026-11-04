# Incident runbook

For whoever is on call. TarangYukti gives safety advice at sea, so the first rule is: **when in doubt, switch
free-form chat off and let official warnings speak** — buttons, map, alerts and morning briefs keep working from
the Constraint Ledger and approved phrases.

## Who

| Role | Holder (solo build) | Contact |
|---|---|---|
| Incident lead / on call | Project owner | on-call e-mail and SMS in the `ty-oncall` action group |
| Grievance officer | See `config/governance.yaml` (sample until appointed) | Me → Help in the app |
| CERT-In | Indian Computer Emergency Response Team | incident@cert-in.org.in · report **within 6 hours** of noticing a reportable incident (CERT-In Directions, 28 Apr 2022) |

## First 15 minutes

1. **Acknowledge** the page; open Application Insights (`ty-ai`) → Failures, and the admin console → Overview.
2. **Decide the switch** (admin → Kill switches, reason required, audit-logged):
   - wrong or unsafe answers, prompt injection, LLM spend spike → **Free-form chat off**
   - alert storm or wrong alerts for a harbour → **Pause non-critical alerts** for that harbour (official warnings
     and border alarms still go out)
3. **Contain**: roll back a bad release — `az containerapp revision list -g ty-live -n <app> -o table`, then
   `az containerapp revision activate -g ty-live -n <app> --revision <previous>`.
4. **Record** what you saw and did (time-stamped) in the incident note.

## Common cases

| Symptom | Check | Action |
|---|---|---|
| Health check failing from 2+ locations | `az containerapp logs show -g ty-live -n ty-channels --follow` | Roll back; restart revision; check Supabase status |
| Answers say "data is old" (H8) | Admin → Data sources | Source down: tools fall back to the snapshot automatically; pin a fresh snapshot (`make snapshot`) |
| Pushes failing | Admin → Alerts (failed in red), `ty-outbox` job runs | Retry; check VAPID / Expo token secrets; 404/410 subscriptions are removed automatically |
| Wrong verdict reported | Admin → Replay with the answer id | Add to failures dataset; fix through a PR with `safety-hold`; never hot-edit thresholds |
| Personal data exposure suspected | Audit log → *Verify chain*; RLS tests (`make test-rls`) | Treat as a breach: CERT-In within 6 h; DPDP Board and affected users without delay |
| Gemini or Sarvam outage | Guardrail review: template fallbacks rising | Nothing to do — buttons answer from the ledger; consider chat off to avoid "needs network" replies |

## After

- Within 7 days: AI incident review (spec §9.5) — new rows in `tests/failures/failures.yaml`, config or prompt
  changes through change control, a line in `docs/releases.md`.
- Keep logs: Log Analytics retains 180 days in Central India (CERT-In).
