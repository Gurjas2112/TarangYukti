# S-02 · Sindhi replies are written in Devanagari

**Found:** 2026-11-05, promptfoo language suite (Milestone 10a) and traced improvement runs `148f31841952` and
`64b7c460a0ec` (Sindhi same_language 0.333 → 0.0; every Sindhi reply is now translated, in Devanagari).

**What happens.** `config/languages.yaml` records Sindhi as Perso-Arabic (`script: Arab`, right-to-left), but
Sarvam-Translate returns Sindhi in Devanagari. The spec (§6.5) notes that the caller cannot choose the output script,
and that each Group B language's script is fixed by its reviewers when they sign the phrase file.

**Not a code fix.** Sindhi is written in both scripts in India. The decision belongs to Sindhi's two native-speaker
reviewers: either keep Perso-Arabic (then free-form replies need a transliteration step, and the reviewers check it)
or record Sindhi as Devanagari in `config/languages.yaml` (left-to-right, Noto Sans Devanagari).

Status: **open — waiting for the Sindhi reviewers.** Sindhi is a draft language and is not shown in production.
