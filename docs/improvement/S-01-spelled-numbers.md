# S-01 · Spelled-out numbers sent replies back to English

**Found:** 2026-11-05, traced improvement run `148f31841952` (86 runs, every language).
**Evidence:** `docs/improvement/runs/148f31841952-20261105-1757.json`, runs `ml-IN-mz-eez`, `mni-IN-mz-eez`,
`pa-IN-mz-territorial`, `sat-IN-mz-territorial` (TraceRoot traces tagged `lang:<code>` in environment `local-eval`).

**What happened.** Questions about the Maritime Zones Act were answered in English for Malayalam, Manipuri,
Punjabi and Santali users. The validated English draft said "twelve nautical miles" and "two hundred nautical
miles"; Sarvam-Translate wrote 12 and 200. The translation number check (`language._numbers`) saw figures the draft
did not have and, as designed, sent the English sentence instead.

**Fix (commit "S-01").** `language.numbers_match`: a translation keeps every number of the draft digit for digit and
may write a number the draft spelled in words; any other new or dropped number still falls back to English.
Permanent test: `tests/failures/failures.yaml` row **F-006**, and `apps/agent/tests/test_languages.py`.

**Proof (same questions, traced):**

| Language | same_language before (`148f31841952`) | after (`64b7c460a0ec`) |
|---|---|---|
| ml-IN | 0.667 | 1.0 |
| mni-IN | 0.667 | 1.0 |
| pa-IN | 0.667 | 1.0 |
| sat-IN | 0.667 | 1.0 |

Status: **closed**.
