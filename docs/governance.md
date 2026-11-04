# Governance

Who may change TarangYukti's behaviour, and how (spec §9.5). Built solo: one person holds every role (Annexure I),
so a 24-hour `safety-hold` replaces the second reviewer. External reviewers are still required for languages
(two native speakers per language) and for the security audit.

| Role | Owns | Holder |
|---|---|---|
| Safety owner | `config/constraints.yaml`, `config/boats.yaml`, `config/qc.yaml`, `config/harbours.yaml` | Project owner |
| Language owner | `config/phrases/`, `config/languages.yaml`, `config/aliases.yaml`, `apps/app/src/i18n/` | Project owner; per-language reviewers to be named |
| AI owner | `apps/agent/src/prompts/`, `ORCA_MODEL`, `EMBED_MODEL`, `RAG_MIN_SIM`, planner effort | Project owner |
| Data owner | `config/sources.yaml`, `kb/sources/`, quarantine queue | Project owner |
| Privacy / grievance officer | DPIA, consent text, data requests, `config/governance.yaml` | Sample contact until appointed |
| Incident lead | `docs/incident-runbook.md`, kill switches | Project owner |
| Release owner | EAS project, release keystore, Play Console, `android-release.yml` | Project owner |

## How a governed change ships

1. A pull request touching a governed file (CODEOWNERS lists them).
2. The `governance` workflow checks it: governed configs bump their `version:`; phrases, prompts and model settings
   add a line to `docs/releases.md`; every governed file has a code owner. The PR carries the `safety-hold` label
   and stays red until 24 hours after its last commit.
3. Gates: unit and property tests, the failures dataset, `make eval-rag`, red-team suite (Milestone 13).
4. Merge; deployment waits for the `live` environment approval.

Kill switches (admin console): free-form chat off; non-critical alerts paused per harbour. Both require a reason and
are audit-logged.
