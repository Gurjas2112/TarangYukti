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
