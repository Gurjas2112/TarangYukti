# Agent improvement report

The improvement loop of spec §10.4: test traffic only (golden sets, cross-language set, promptfoo, the failures
dataset), traced into TraceRoot Cloud (environment `local-eval`), scored by `scripts/eval_traceroot.py` and judged by
the detectors in `docs/improvement/detectors.md`. Real figures only; every number below comes from a run file in
`docs/improvement/runs/`.

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
| [S-01](S-01-spelled-numbers.md) | Spelled-out numbers ("twelve") became digits in translation; replies fell back to English | Closed — same_language 0.667 → 1.0 for ml, mni, pa, sat (failures row F-006) |
| [S-02](S-02-sindhi-script.md) | Sindhi is translated into Devanagari while the configuration says Perso-Arabic | Open — script decision for the Sindhi reviewers |

**Detectors (TraceRoot LLM judges):** the six detectors of `detectors.md` are defined but not yet created in the
TraceRoot project (they are added in the TraceRoot UI, Detectors → New Detector). Their rates will be reported here
once they have judged a run; until then the deterministic checks above are the measured figures.

**Before/after for S-01** (same questions, traced):

| Language | before | after |
|---|---|---|
| ml-IN · mni-IN · pa-IN · sat-IN | 0.667 | 1.0 |
| sd-IN | 0.333 | 0.0 (S-02: every reply now translated, in Devanagari) |
