# Releases and governed changes

Every change to safety thresholds, phrases, prompts, sources or model settings gets a line here (spec §9.5):
what changed, why, the evaluation, and who approved it. Solo build (Annexure I): the owner approves after the
24-hour `safety-hold`; external reviewers are still required for languages and the security audit.

| Date | Change | Why | Evaluation | Approver |
|---|---|---|---|---|
| 2026-11-03 | `constraints.yaml` v3: H1 also blocks on state disaster authority (SDMA) alerts | SDMAs relay and issue coastal alerts; blocking is the conservative choice | Yukti property tests | Owner (decision recorded in README, Milestone 3) |
| 2026-11-04 | Planner reasoning effort `low` (`ORCA_PLANNER_EFFORT`) | medium/high exceeded the 20 s LLM timeout (failures row F-003) | `make test-local`; failures harness | Owner |
| 2026-11-04 | Phrase files for all 23 languages drafted with `sarvam-translate:v1` (`status: draft`) | Every language needs a phrase file; drafts are never released | Phrase key/slot tests; untranslated keys listed in `apps/app/src/i18n/drafts.json` | Pending: two native-speaker reviewers per language |
| 2026-11-04 | `constraints.yaml` v4: `pfz_compute` and `heatwave` thresholds; `sources.yaml` v6: OISST anomaly + MUR SST | Analyst tools (Milestone 7); OISST 0.25° too smooth for fronts | Ocean tool tests; live run (4 zones, +1.79 °C anomaly) | Owner |
| 2026-11-04 | `harbours.yaml` v2: 1.5 km geofence; phrases: border/park alerts, trip, family | Trips and alerts (Milestone 8) | Trip rule tests; live simulated trip | Owner |
| 2026-11-04 | Phrases: `chat_paused` (kill switch); `governance.yaml` v1 (grievance officer placeholder) | Milestone 9 | Agent record tests; RLS tests | Owner — grievance contact still to be named |
| 2026-11-04 | `governance.yaml` v2: sample grievance officer (`grievance@example.org`) | Help must name a contact; the real one is still to be appointed | `/help` returns it | Owner — replace before any real user |
