# Agent improvement report

The improvement loop of spec §10.4: test traffic only (golden sets, cross-language set, promptfoo, the failures
dataset), traced into TraceRoot Cloud (environment `local-eval`), scored by `scripts/eval_traceroot.py` and judged by
the detectors in `docs/improvement/detectors.md`. Real figures only: every number below comes from a traced run (TraceRoot project, environment `local-eval`,
candidate versions named by git SHA).

## 2026-11-05 · candidate `148f31841952` → `64b7c460a0ec`

**Runs traced:** 86 (3 golden questions per language for 22 languages — 2 answerable, 1 the corpus cannot answer —
plus 20 cross-language, code-mixed questions) and 15 after the fix (the five affected languages).
Model `gemini-3.8-flash`, every language a **draft** (none released yet).

| Check | Rate, all 86 runs |
|---|---|
| Reply ends with the language's approved "advisory only" footer | 1.00 |
| No "safe" without "advisory" | 1.00 |
| Draft needed no validator repair (no ungrounded number, dropped quote or language mismatch) | 1.00 |
| Answered by the agent, not the fallback template | 1.00 |
| Unanswerable questions got no figures | 1.00 |
| Reply in the requested language's script | 0.93 (6 of 86 failed: Sindhi 2, Malayalam, Manipuri, Punjabi, Santali 1 each) |

**Signals**

| Signal | Problem | Status |
|---|---|---|
| S-01 | Spelled-out numbers ("twelve") became digits in translation; replies fell back to English | Closed — same_language 0.667 → 1.0 for ml, mni, pa, sat (failures row F-006) |
| S-02 | Sindhi is translated into Devanagari while the configuration says Perso-Arabic | Open — script decision for the Sindhi reviewers |

**Detectors (TraceRoot LLM judges):** the six detectors of `detectors.md` are defined but not yet created in the
TraceRoot project (they are added in the TraceRoot UI, Detectors → New Detector). Their rates will be reported here
once they have judged a run; until then the deterministic checks above are the measured figures.

**Before/after for S-01** (same questions, traced):

| Language | before | after |
|---|---|---|
| ml-IN · mni-IN · pa-IN · sat-IN | 0.667 | 1.0 |
| sd-IN | 0.333 | 0.0 (S-02: every reply now translated, in Devanagari) |

## Signal details

### S-01 · Spelled-out numbers sent replies back to English

**Found:** 2026-11-05, traced improvement run `148f31841952` (86 runs, every language).

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

### S-02 · Sindhi replies are written in Devanagari

**Found:** 2026-11-05, promptfoo language suite (Milestone 10a) and traced improvement runs `148f31841952` and
`64b7c460a0ec` (Sindhi same_language 0.333 → 0.0; every Sindhi reply is now translated, in Devanagari).

**What happens.** `config/languages.yaml` records Sindhi as Perso-Arabic (`script: Arab`, right-to-left), but
Sarvam-Translate returns Sindhi in Devanagari. The spec (§6.5) notes that the caller cannot choose the output script,
and that each Group B language's script is fixed by its reviewers when they sign the phrase file.

**Not a code fix.** Sindhi is written in both scripts in India. The decision belongs to Sindhi's two native-speaker
reviewers: either keep Perso-Arabic (then free-form replies need a transliteration step, and the reviewers check it)
or record Sindhi as Devanagari in `config/languages.yaml` (left-to-right, Noto Sans Devanagari).

Status: **open — waiting for the Sindhi reviewers.** Sindhi is a draft language and is not shown in production.
