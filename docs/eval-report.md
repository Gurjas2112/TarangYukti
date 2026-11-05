# Evaluation report

Dated results of `make eval-rag` (retrieval) and, from Milestone 5, the answer-quality runs.

## RAG retrieval evaluation — 2026-11-03T15:51:44+00:00

Golden set: 60 questions. Gate: recall@8 ≥ 0.9 — **passed** (overall 0.958).

| Measure | Value |
|---|---|
| recall@8 (en-IN) | 0.958 |
| recall@8 (ta-IN) | 0.958 |
| unanswerable recognised (en-IN) | 1.0 |
| unanswerable recognised (ta-IN) | 1.0 |
| best similarity, answerable | {'min': 0.752, 'median': 0.808, 'max': 0.863} |
| best similarity, unanswerable | {'min': 0.53, 'median': 0.605, 'max': 0.665} |
| RAG_MIN_SIM current / suggested | 0.7 / 0.709 |

Ragas faithfulness and answer relevancy need generated answers; they run with the agent (Milestone 5).

Misses:

- `en-ban-east-coast` When is the annual fishing ban on the east coast? — expected ['dof:fishing-ban'], got ['act:tn-marine-fishing-regulation-2017-amendment', 'act:tn-marine-fishing-regulation-2017-amendment', 'act:tn-marine-fishing-regulation-1983']
- `ta-ban-east-coast` கிழக்குக் கடற்கரையில் ஆண்டு மீன்பிடி தடைக்காலம் எப்போது? — expected ['dof:fishing-ban'], got ['act:tn-marine-fishing-regulation-2017-amendment', 'act:tn-marine-fishing-regulation-1983', 'act:tn-marine-fishing-regulation-2017-amendment']

## RAG retrieval evaluation, every language — 2026-11-05

Golden sets of Milestone 10a: 20 machine-drafted questions for each of 21 languages (16 answerable, 4 the corpus
cannot answer; `apps/agent/tests/golden/<code>.jsonl`, pending native-speaker review) and 20 code-mixed
cross-language questions (`golden/cross.jsonl`). 440 questions, `kb_hybrid_search` with the cache off, measured with
`python -m tarangyukti.rag.eval --golden <file>`. Gate: recall@8 ≥ 0.9.

| Set | recall@8 | unanswerable recognised |
|---|---|---|
| doi, gom, gu, hi, kn, ks, mai, ml, mni, mr, ne, or, pa, sat, sd, te, ur | 0.938 each | 1.00 each |
| sa | 0.938 | 0.75 |
| as, bn, brx | 0.875 each | 1.00 each |
| cross (code-mixed) | 0.833 | 1.00 |
| **mean** | **0.925** | |

**Why the misses happen.** 24 of the 30 misses are one question, "When is the annual fishing ban on the east
coast?", in every language: its source, the Department of Fisheries ban order (PIB release 2114930), is **not in the
index** because PIB refuses automated clients and the page has not been saved by hand yet
(`kb/sources/captured/pib-2114930.html`, see `kb/sources/manifest.yaml`). The retriever returns the Tamil Nadu
Marine Fishing Regulation Act instead, which is the closest document present. Without that question every language
set is at or above the gate except the cross set (0.875: the Kachchatheevu question in Telugu script with English
names). The remaining real weakness is the "official high wave warning" question in Assamese, Bengali and Bodo (the
safety SOP is not retrieved).

**Next:** save the PIB page and re-index (`make kb-index`), then re-run; add Assamese, Bengali and Bodo spellings of
"high wave warning" to `config/aliases.yaml` once their reviewers confirm the terms.
