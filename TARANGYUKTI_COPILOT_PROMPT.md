# TarangYukti — Build Prompt for GitHub Copilot (coding agent)

> **How to use this file**
> - Save it twice in the repo: `.github/copilot-instructions.md` (Copilot reads it on every request) and `AGENTS.md` at the root (Copilot coding agent, Cursor, Claude Code and others read it).
> - Keep `docs/TarangYukti_Engineering_Specification_v2.0.md` in the repo. This prompt is the build contract; the specification has the reasoning, diagrams and full detail. **If the two disagree, the specification wins.**
> - Assign **one milestone per issue / pull request**, e.g. *"Implement Milestone 3 from AGENTS.md"*. Never attempt the whole system in one task.
> - This file replaces `ORCA_COPILOT_PROMPT.md`.

---

## 1. Role and goal

You are a senior full-stack engineer building **TarangYukti** (तरंग *wave* + युक्ति *reasoning*): a constraint-reasoning marine copilot over ISRO/INCOIS ocean data. It is a prototype for **Smart India Hackathon 2026, ISRO problem statement 26176 — "ORCA: Marine EcOsystem Reasoning with Collaborative Agents"**.

Users ask in Tamil or English, by voice or text: *"Can I go to sea tomorrow morning?"*, *"Where is the nearest fishing zone?"*, *"Why has catch dropped here?"*. TarangYukti answers in the same language and gives a verdict with its reasons. It also **pushes** a morning brief before departure, warns near the India–Sri Lanka border line (IMBL) and protected areas, and tells the family when the boat is back.

**Prototype scope — do not exceed:**

- **Region:** Gulf of Mannar + Palk Bay only (bbox lon 78.0–80.5, lat 8.0–10.5; home harbour Rameswaram 9.288 N, 79.313 E).
- **Languages:** Tamil + English end to end; the language layer must accept any of the 22 scheduled languages.
- **Channels:** the **Kadal Mitra PWA** (installable Simple-mode route `/m` of the Next.js app, with web push) and the web console. No Telegram or any chat bot.
- **Primary run target:** a single Windows 11 laptop (WSL2 Ubuntu 22.04, i7-11800H, 16 GB RAM, RTX 3060 6 GB). The demo must work **offline**.
- **Public showcase:** Vercel (web) + Render Singapore (Python) + Supabase Mumbai + Neo4j AuraDB Free.

---

## 2. Non-negotiable rules

1. **The LLM never produces a number.** Every wave height, distance, time, coordinate and temperature in a reply comes from a tool result carrying `source` and `fetched_at`. A validator rejects replies with ungrounded numbers.
2. **Constraints decide; the LLM explains.** Go / Caution / No-Go comes from the deterministic Yukti constraint engine. Every refusal names its constraint (e.g. `H2`) and evidence.
3. **Official warnings win; never say "safe".** An active INCOIS/IMD warning forces NO-GO. The best verdict is "GO — no constraint violated, advisory only". Every answer ends with "Advisory only — follow official INCOIS/IMD warnings."
4. **Same language in and out.** Detect once, store in thread state, reply in it.
5. **Simple mode by default.** Fishers, families and the public get plain words, a verdict card and four buttons. Codes (PFZ, IMBL, H1–H8), the ledger, Mission Control and sliders appear only in Expert mode.
6. **Safety wording comes from approved phrases.** Simple-mode replies fill slots in `config/phrases/{ta,en}.yaml`. Never let the LLM invent safety sentences.
7. **Public answers need no login.** Login is only for personal features (boats, live location, family sharing, alert subscriptions) and staff roles.
8. **Personal data stays in Supabase Postgres under RLS.** Never put phone numbers, names or raw coordinates in Redis, Neo4j, logs or traces. Caches key by H3 cell.
9. **Snapshot mode always works.** `DATA_MODE=snapshot` reads the dated snapshot from the Supabase Storage bucket `snapshots`, so the demo runs without data-source APIs.
10. **Small, typed, tested.** Python 3.12 with type hints and Pydantic v2 strict models. TypeScript strict with Zod. Every milestone ships with tests.

---

## 3. Fixed tech stack (use exactly these)

| Layer | Pick |
|---|---|
| Monorepo base | Clone `https://github.com/CopilotKit/with-langgraph-python`; rename `apps/app` → `apps/web` |
| Python packaging | `uv` (one `pyproject.toml` + `uv.lock` per service) |
| Agents | LangGraph 1.x + LangChain 1.x `create_agent`; supervisor via **tool-calling** (sub-agents wrapped as `@tool`); **not** `langgraph-supervisor` |
| LLM | Gemini via `langchain-google-genai`, model from `ORCA_MODEL` (default `gemini-3.8-flash`), `temperature=0`. Fallback: Ollama `qwen3.5:4b` via `langchain-ollama` after `LLM_TIMEOUT_S` or when `LLM_MODE=local_only`; then templates |
| Tools | FastMCP servers (streamable HTTP); agents connect with `langchain-mcp-adapters` `MultiServerMCPClient` |
| Reasoning | Yukti constraint engine (custom Python, Section 6) + time-expanded A* on H3 |
| RAG | Docling + HybridChunker → bge-m3 embeddings (Ollama) → Postgres pgvector HNSW + full-text (`simple` config) + PostGIS filters → RRF → `BAAI/bge-reranker-v2-m3` (sentence-transformers `CrossEncoder`, fp16 on GPU) |
| Speech | Sarvam `sarvamai`: STT `saaras:v4` (mode `codemix`, keyterms), TTS `bulbul:v3` (`mp3`), text translate |
| Phone channel + push | Next.js PWA per the official guide (`app/manifest.ts` + hand-written `public/sw.js`, no plugin); Web Push with VAPID: `pushManager.subscribe` in the browser, **pywebpush** in the worker; keys from `npx web-push generate-vapid-keys` |
| Web | Next.js 16 (App Router) + CopilotKit (`@copilotkit/react-core`, `react-ui`, `runtime`) + MapLibre GL + deck.gl + PMTiles + Tailwind v4 + shadcn/ui + Recharts + TanStack Query + React Hook Form + Zod |
| Auth / DB / files | Supabase: Auth (**Google sign-in only**, also on the phone; "Add this phone" QR = one-time `token_hash` from `auth.admin.generate_link` verified with `verifyOtp`; TOTP MFA for staff), Postgres 17 + PostGIS + pgvector, RLS, Storage |
| Evidence graph | Neo4j 5 (local container; AuraDB Free in showcase) — Constraint Ledger only. **Never create vector indexes in Neo4j** |
| Cache | **`ty_common.cache`** — one two-tier cache for every service: L1 **cachetools** `TTLCache` in-process + L2 **Redis 7** via `redis.asyncio` (local container; Render Key Value in showcase) + **orjson**. JSON only, never pickle (Section 7a) |
| Geo / science | xarray, netCDF4, copernicusmarine, GeoPandas, Shapely, h3 (v4), NetworkX, scikit-image, pyarrow |
| Scheduling | APScheduler in one `worker` process locally; Render cron jobs in the showcase (same run-once functions) |
| Observability | OpenTelemetry → `grafana/otel-lgtm` container; `openinference-instrumentation-langchain`; `@vercel/otel`. **No LangSmith** |
| Quality | pytest, pytest-asyncio, Hypothesis, respx, fakeredis, Schemathesis, Playwright, Ragas, promptfoo, Ruff, mypy, ESLint, `tsc --noEmit` |
| Hosting | Laptop: native processes in WSL + Docker Engine (not Docker Desktop) for infra. Showcase: Vercel `sin1` + Render Singapore Blueprint (`render.yaml`) |

---

## 4. Repository layout (create exactly this)

```
tarangyukti/
├── apps/
│   ├── web/                      # Next.js 16
│   │   ├── src/app/(public)/     # Simple mode home (no login)
│   │   ├── src/app/expert/       # Expert console (map, ledger, citations, Mission Control, slider)
│   │   ├── src/app/me/           # boats, harbour, alerts, family, my data, mode switch
│   │   ├── src/app/analyst/      # MFA
│   │   ├── src/app/officer/      # MFA
│   │   ├── src/app/admin/        # MFA
│   │   ├── src/app/api/copilotkit/route.ts
│   │   ├── src/components/       # VerdictCard, FourButtons, WhySheet, TimeRibbon, ConstraintLedger,
│   │   │                         # CitationChip, MissionControl, OceanMap, DepartSlider
│   │   ├── e2e/ · promptfoo/
│   │   └── package.json          # name "@repo/web"
│   ├── mobile/                   # Expo SDK 57 Android app "Kadal Mitra" — Milestone 11 only (pilot stage)
│   └── agent/                    # LangGraph
│       ├── main.py               # async make_graph()
│       ├── src/agents/           # language, planner, discovery, weather, ocean, geo, knowledge, yukti, explain
│       ├── src/prompts/          # one .md per agent; planner prompt first and stable (≥ 4,096 tokens incl. tool schemas)
│       ├── src/validator.py
│       └── langgraph.json        # {"graphs": {"orca": "./main.py:make_graph"}}
├── services/
│   ├── mcp/                      # uv package name "tarangyukti" (avoids clashing with the `mcp` library)
│   │   └── src/tarangyukti/{server.py, cache.py, tools/, yukti/, route.py, rag/, qc.py, phrases.py}
│   ├── channels/                 # package "ty-channels": voice/device API — /stt, /tts, /positions, /push/subscribe, /trips, /phone-link
│   └── worker/                   # package "ty-worker": ingest, kb_index, watch (brief, trips, alerts)
│       └── src/ty_worker/{__main__.py, ingest_once.py, kb_index.py, watch_once.py}
├── packages/ty-common/           # auth (JWKS), settings, OTel setup, ToolResult, cache (@cached); editable path dependency
├── supabase/                     # config.toml, migrations/, seed.sql
├── infra/docker-compose.yml      # neo4j, redis, otel-lgtm (laptop)
├── docker/                       # Dockerfile.python, Dockerfile.embed, Dockerfile.web
├── config/                       # constraints.yaml, boats.yaml, qc.yaml, sources.yaml, phrases/ta.yaml, phrases/en.yaml
├── kb/sources/                   # allow-listed document manifests
├── ops/grafana/                  # dashboards + alert rules
├── scripts/                      # demo.sh, smoke.sh, db_roles.sh, sim_boat.py, sim_warning.py, grafana_provision.sh
├── docs/                         # specification, eval-report.md, test-report.md, incident-runbook.md
├── render.yaml · Makefile · README.md · THIRD_PARTY.md · .env.example · AGENTS.md
└── .github/{copilot-instructions.md, workflows/ci.yml}
```

---

## 5. Environment variables (`.env.example`)

```dotenv
ENV=local
# Supabase
SUPABASE_URL=http://127.0.0.1:54321
DATABASE_URL=postgresql://ty_api:<password>@127.0.0.1:54322/postgres          # no BYPASSRLS
WORKER_DATABASE_URL=postgresql://ty_worker:<password>@127.0.0.1:54322/postgres
SUPABASE_SERVICE_ROLE_KEY=                                                     # channels + worker only
# LLM
GOOGLE_API_KEY=
ORCA_MODEL=gemini-3.8-flash
LLM_MODE=cloud                       # falls back to qwen3.5:4b automatically after LLM_TIMEOUT_S
OLLAMA_HOST=http://127.0.0.1:11434
LLM_LOCAL_MODEL=qwen3.5:4b
LLM_TIMEOUT_S=20
# RAG
EMBED_MODEL=bge-m3
RERANK_MODEL=BAAI/bge-reranker-v2-m3   # showcase sets "none"
RERANK_DEVICE=cuda                     # showcase sets cpu
RAG_MIN_SCORE=0.3
# Speech, push
SARVAM_API_KEY=
VAPID_PUBLIC_KEY=                      # npx web-push generate-vapid-keys --json; same value as NEXT_PUBLIC_VAPID_PUBLIC_KEY
VAPID_PRIVATE_KEY=                     # worker only, never in the browser
VAPID_SUBJECT=mailto:
# Data
DATA_MODE=online                       # demo.sh and the showcase set snapshot
SNAPSHOT_DATE=                         # YYYY-MM-DD folder in Supabase Storage bucket "snapshots"
COPERNICUSMARINE_SERVICE_USERNAME=
COPERNICUSMARINE_SERVICE_PASSWORD=
GFW_API_TOKEN=
# Graph, cache
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=
REDIS_URL=redis://:<password>@127.0.0.1:6379/0
REDIS_PASSWORD=
CACHE_DISABLED=0                       # 1 bypasses both cache tiers (debugging only)
# Wiring, telemetry
MCP_URL=http://127.0.0.1:8001/mcp      # on Render: built from MCP_HOSTPORT
AGENT_URL=http://127.0.0.1:8123        # on Render: built from AGENT_HOSTPORT
WEB_ORIGIN=http://localhost:3000
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
```

Read config through one settings module per service: `pydantic-settings` in `ty-common`, a Zod-validated `env.ts` in web. If `MCP_URL`, `AGENT_URL` or `OLLAMA_HOST` is unset and the matching `*_HOSTPORT` is set (Render), build `http://<hostport>` (+ `/mcp` for MCP). Never commit real values.

---

## 6. The Yukti constraint engine (signature reasoning)

**Loop:** gather facts (tools + `kb_search`) → propose candidates (departure windows × routes × zones) → check hard constraints → repair (drop violating cells, shift the window by 30 min, next zone) → score soft constraints → best feasible option + Constraint Ledger → explain.

**Catalogue:** `config/constraints.yaml`, thresholds as data, not code.

| ID | Kind | Rule |
|---|---|---|
| H1 | hard | No active INCOIS/IMD warning covers the cell in the trip window → NO-GO, cite the warning |
| H2 | hard | Route ≥ `imbl_min_km` (5) from the IMBL |
| H3 | hard | No fishing inside the Gulf of Mannar Marine National Park |
| H4 | hard | No PFZ advice to mechanised boats during the EEZ ban (east 15 Apr–14 Jun; non-motorised exempt) |
| H5 / H6 | hard | Wave / wind within the boat profile for the whole window (`config/boats.yaml`) |
| H7 | hard | No IMD thunderstorm nowcast for the district in the window |
| H8 | hard | Every input within its freshness limit, else that part is "unknown" — never GO |
| S1–S5 | soft | PFZ score + INCOIS agreement; fuel margin 20%; risk margin (CAUTION at ≥ 0.6); back before sunset for small boats; sources agree within 0.5 m |

**Outcome:** any hard fail → NO-GO / rejected; all hard pass and risk ≥ 0.6 → CAUTION; else GO (advisory).

**Code shape:** `@constraint("H2", "hard", ("route",))` registers a function `(ctx, params) -> Verdict(ok, value, unit, evidence)`. `evaluate(ctx, candidate)` returns `{"feasible": bool, "ledger": [...]}`.

**Search:** departure times in 30-minute steps over 24 h. For each one, run the time-expanded A* (`route.py`):

- nodes are `(h3_res7_cell, time_step)`, with a priority queue of `(g + h, g, cell, t, path)`;
- H2/H3 cells are removed;
- a node whose forecast at that time step violates H5–H7 is skipped;
- the heuristic is straight-line km.

**Ledger:** written to Neo4j as `(:Answer)-[:CHECKED]->(:ConstraintResult)-[:BASED_ON]->(:Observation)-[:FROM]->(:Dataset)` and `(:Answer)-[:CITES {quote}]->(:Chunk {id, version})`. It stores pseudonymous thread ids only; chunk ids are plain values pointing to Postgres.

- **Locked schema:** only these 5 labels and 4 relationship types (`LEDGER_LABELS`, `LEDGER_RELS` in `tarangyukti/ledger.py`), checked before every `MERGE`. No LLM ever writes Cypher.
- **Two times per fact:** every `Observation` stores `valid_at` (when the value is true; from `ToolResult.valid_at`) and `known_at` (when it was fetched; from `ToolResult.fetched_at`). Never overwrite; replay a past answer with `WHERE o.known_at <= a.at`.

**"Why has catch dropped?"** Each candidate cause is accepted only if its data test passes, using thresholds from YAML:

- marine heatwave;
- low chlorophyll;
- weather days lost;
- a change in GFW fishing effort;
- the CMFRI landings trend.

Causes whose data is missing are returned as "not tested — data unavailable".

---

## 7. Data tools (FastMCP) and contract

Every tool returns:

```python
class ToolResult(BaseModel):
    data: dict | list
    source: str
    source_url: str
    fetched_at: datetime          # stored UTC, shown IST
    confidence: Literal["high", "medium", "low"]
    cache: Literal["miss", "hit", "stale", "snapshot"]
    notes: list[str] = []
```

**Tools:**

- `marine_forecast`, `imd_warnings`, `incois_alerts`
- `sst_grid`, `chl_grid`, `anomaly_series`
- `pfz_incois`, `pfz_compute` (Sobel SST fronts ∩ chlorophyll above threshold, plus overlap score vs INCOIS)
- `fence_check`, `geo_distance`, `route_safest`
- `fishing_effort` (GFW 4Wings, `Authorization: Bearer`)
- `kb_search`, `yukti_evaluate`, `my_boats` (runs with the caller's JWT so RLS applies)

**Sources:**

| Source | Access | Used by |
|---|---|---|
| Open-Meteo Marine + Forecast | No key | Waves, swell, currents, wind |
| IMD API `https://api.imd.gov.in/api/v1/` | IP-whitelisted | `portwarning`, `seabulletin`, `coastalbulletin`, `districtnowcast`, `sunmoon` |
| INCOIS PFZ / OSF pages | Parsed into snapshots | PFZ ground truth, OSF cross-check |
| INCOIS ERDDAP | Open | Indian ocean grids |
| MOSDAC | Registration | ISRO satellite products |
| NOAA CoastWatch ERDDAP | Open | `ncdcOisst21Agg` (SST), `erdMH1chla1day_R2022NRT` (chlorophyll) |
| Copernicus Marine | Account | Backup grids |
| Global Fishing Watch | Token | Fishing effort |
| Boundaries | Downloads | Marine Regions EEZ, LIS-77 IMBL, WDPA MPA, GEBCO |

Fetch only from domains in `config/sources.yaml`. Run QC from `config/qc.yaml` (ranges, NaN/cloud masks, freshness) before returning.

**Cache:** every tool is wrapped with `@cached(ns="tool", ...)` from `ty_common.cache` (Section 7a). TTLs: warnings 300 s, forecasts 3600 s, PFZ until next issue (max 86400), SST/chl 86400, layers 30 days.

**Snapshots:** `make snapshot DATE=YYYY-MM-DD` writes every source plus a SHA-256 `manifest.json` to Supabase Storage bucket `snapshots/<date>/`; `DATA_MODE=snapshot` reads only from there.

## 7a. Unified cache — `ty_common.cache` (use it everywhere; never write another cache)

**One decorator:** `@cached(ns, ttl, key, tags=None, l1=True)` in `packages/ty-common/src/ty_common/cache.py`. Any service may use it: agent, mcp, channels, worker.

**Keys are content-addressed.** `key = f"{ns}:v{schema}:" + sha256(orjson.dumps([input data versions, config version, normalised args], OPT_SORT_KEYS))`.

- **Input data versions:** each `ToolResult`'s source plus upstream issue time or payload SHA-256. New data gives a new key, so stale data is never served from an old key.
- **Config version:** SHA-256 of `constraints.yaml`, `boats.yaml`, `qc.yaml` and the phrase files, computed at start-up.
- **Normalisation before hashing:** lat/lon → H3 res-7 cell; time → hour or 30-min window; text → NFC, trimmed (lower-cased for embedding keys).

**Behaviour:**

- **Read path:** L1 → L2 → compute; an L2 hit fills L1.
- **Stampede lock:** `SET lock:{key} NX EX 30`. Only the owner computes and deletes the lock; others wait ≤ 2 s, then return `lastgood`.
- **Early refresh:** in the background at 80% of the TTL.
- **Stale-if-error:** `lastgood:{key}` has no TTL and is returned with `cache="stale"`.
- **Tags:** one Redis set per tag; `invalidate(tag=...)` deletes the keys.
- **L1 invalidation:** broadcast on the pub/sub channel `ty:cache:inv`.
- **Limits:** L1 holds 2,000 entries and values ≤ 64 KB; L2 runs `allkeys-lru`.
- **Metrics:** OTel `ty.cache.result{ns,tier,outcome}`.
- **Kill switch:** `CACHE_DISABLED=1`.

**Cache map (implement all):**

| ns | What | Key inputs | TTL / store |
|---|---|---|---|
| `tool` | Data tool results | tool, H3 cell, hour, source version | as above |
| `layer` | Fence flags per H3 cell | layer SHA, cell | 30 days |
| `yukti` | Constraint evaluation + ledger | input versions, config version, cell, boat type, window | 15 min |
| `route` | Safest route | start cell, goal cell, boat type, departure step, input versions | 15 min |
| `emb` | Query embeddings | sha256(text), embed model | 7 days |
| `kb` | Hybrid search + rerank result | query hash, H3 cell, hour, `index_version` | 10 min |
| `tr` | Sarvam translation of approved phrase renderings | sha256(text), target language | 30 days |
| `tts` | Sarvam TTS audio | sha256(text), voice, model | Supabase Storage object + 30-day Redis pointer |
| `img` | Static map images for push-opened and offline briefs | sha256(layers, route, verdict) | Storage object + 24 h pointer |
| `brief` | Rendered Simple-mode brief per (harbour, boat type, language, date) | yukti fingerprint, phrase version | until an input version changes |
| `jwks`, `conf` | Signing keys; parsed YAML/phrases | issuer; file SHA | 10 min; process lifetime (L1 only) |

**Rules:**

- Personalise **after** the cache. Name, boat name and the feedback line are added at send time and never stored in a shared entry.
- **Never cache:**
  - free-text LLM replies;
  - personal data (phones, names, coordinates, positions, boats, consents);
  - user speech-to-text;
  - admin/audit queries.
- Simple-mode replies are template renderings of a ledger, so they are cached under the ledger's fingerprint.

**Outside this module:**

- TanStack Query in the browser, plus a Service Worker that caches the last verdict card offline.
- `Cache-Control: public, max-age=60, stale-while-revalidate=300` on public verdict JSON; `private, no-store` on personal routes.
- Versioned PMTiles marked `immutable` on the CDN.
- Gemini implicit prompt caching (stable prompt prefix).


---

## 8. RAG (production-grade)

- **Corpus (allow-listed):**
  - INCOIS PFZ text and OSF/alert bulletins
  - IMD sea-area, coastal and port bulletins
  - Department of Fisheries ban order
  - Tamil Nadu Marine Fishing Regulation Act; Maritime Zones of India Act 1981
  - Gulf of Mannar MNP notes
  - INCOIS PFZ method pages
  - CMFRI *Marine Fish Landings* 2023–2025
  - team-written safety SOPs
- **Ingest (`kb_index`):** fetch → SHA-256 skip if unchanged → sanitise (quarantine injection-like text) → Docling → HybridChunker (≤ 512 tokens) → metadata (issuer, doc_type, language, `valid_from/valid_to`, region polygon) → bge-m3 → upsert; old versions become `superseded`, never deleted while cited; bump `index_version`.
- **Schema:** `kb_documents` (source_id, version, issuer, doc_type, language, url, licence, sha256 unique, valid_from, valid_to, region geography, status, `ingested_at`, `superseded_by` → kb_documents, `superseded_at`; check: status 'superseded' ⇔ superseded_at set) and `kb_chunks` (document_id, ord, heading_path, content, `fts tsvector generated always as (to_tsvector('simple', content)) stored`, `embedding vector(1024)`, embed_model, index_version, `topics text[]` canonical slugs) with HNSW cosine + GIN (fts, topics) + GiST indexes.
- **Supersession across documents:** a newer INCOIS/IMD bulletin or a corrigendum replaces an older one via a parser rule in `config/sources.yaml` or the admin **Supersede with…** action; both set `superseded_by` + `superseded_at`.
- **Query:** `kb_hybrid_search(q_text, q_emb, at, near, k=40, rrf_k=50, known_at=now())` SQL function:
  - filters `status <> 'quarantined'`, `ingested_at <= known_at`, `superseded_at is null or > known_at`, validity at `at`, `ST_DWithin(region, near, 50000)` (so `known_at = now()` means active-only, and a past `known_at` replays exactly what was retrievable then);
  - merges full-text and vector ranks with RRF.
  - Two queries run: the original and an English rewrite. Rerank to top 8 (reranker off in the showcase).
- **Aliases:** `config/aliases.yaml` maps every spelling (Rameshwaram/ராமேஸ்வரம், border line/எல்லைக் கோடு/IMBL, vanjiram/Seer fish) to one slug via `ty_common.aliases.canonical()` (NFKC + whitespace + casefold, no LLM). Used for query normalisation, `kb_chunks.topics` at ingest, and spoken harbour names → harbour id + `near`. Test: every alias maps to exactly one slug.
- **Answer contract:** document-based sentences carry `[K1]…[K8]` **plus a verbatim quote**, returned as structured output `{"marker": "K3", "quote": "…"}`. The validator removes sentences with fake or missing markers **or a quote that is not a verbatim substring of that chunk** (`ty_common.quotes.is_verbatim`: NFKC + curly quotes + whitespace normalised, ≥ 12 chars). Quotes stay in the document's language and are never translated. Simple-mode phrase slots from documents (ban dates etc.) are filled from the verified quote; numbers must appear in the cited chunk or a tool result. If the top score is below `RAG_MIN_SCORE`, say nothing relevant was found and name the official source.
- **Eval:** golden set of 60 questions (30 ta, 30 en) in `apps/agent/tests/golden.jsonl`. `make eval-rag` computes recall@8 and Ragas (faithfulness, context precision, context recall, answer relevancy). Gates: faithfulness ≥ 0.85, recall@8 ≥ 0.9.
- **Cache:** namespaces `emb` and `kb` of `ty_common.cache` (Section 7a).

---

## 9. Agents and validator

Planner + specialists as tools:

- Language
- Data Discovery
- Weather Intel
- Ocean Analytics
- Geospatial
- Knowledge (RAG)
- Yukti (constraints + route)
- Explain & Visualise (ledger write, cards, CopilotKit frontend tools)

The planner calls independent specialists in parallel.

**State (`OrcaState`):** messages, `lang`, `mode` (`simple`|`expert`), `user_id?`, `boat_profile`, `home_harbour`, `last_cell` (H3, not lat/lon), `evidence`, `answer_id`.

**Validator node:**

1. All numbers grounded. Use a regex for numbers with units (m, km, nm, °C, knots, km/h, %, h) and `HH:MM` times; single digits are allowed.
2. Every `[Kn]` is in the retrieved set, and its quote is verbatim in that chunk (dropped quotes are counted as `guardrail.quote_dropped`).
3. Reply language = `lang`.
4. **Simple mode only:** the reply is assembled from `config/phrases/<lang>.yaml` templates and contains none of `PFZ`, `IMBL`, `H1`–`H8`.

On failure, rewrite once; after that, render the template from the ledger.

**Language flow:** draft in English → Sarvam translate → re-run the number check. Offline, qwen writes the reply directly.

Prompts live in `apps/agent/src/prompts/*.md`. The planner prompt + tool schemas come first and stay byte-identical across calls (Gemini implicit caching).

---

## 10. Simple mode and daily-use mechanics (build these before Expert mode)

**Phrases file** (approved wording only; the LLM fills slots):

```yaml
# config/phrases/en.yaml  (ta.yaml has the same keys; Tamil reviewed by fishermen before use)
verdict:
  GO: "Good to go."
  CAUTION: "Go, but carefully — back by {back_by}."
  NO-GO: "Don't go today. Next good time: {next_window}."
why:
  H5: "Waves get too high after {time}."
  H2: "That route goes too close to the border line."
  H1: "There is an official {issuer} warning: {warning_name}."
spot: "Fish likely {distance_km} km {direction}."
border: "Border line is {distance_km} km away."
stale: "Old forecast — check again before leaving."
footer: "Advisory only — follow official INCOIS/IMD warnings."
```

**Mechanics:**

1. **Morning brief (push).**
   - `watch_once` sends each signed-in fisher a **web push 30 min before their usual departure** (median of the last 10 trips; default 04:00 IST). Tapping it opens `/m/brief/<date>`, which auto-plays the Tamil voice.
   - The card shows the verdict, safe window, nearest fish spot and one warning. The service worker saves the brief page in Cache Storage so it opens with no signal.
   - `make brief-now USER=<id>` triggers one immediately (used in the demo).
2. **Four buttons:** a fixed bottom bar in Kadal Mitra and the web console: **Today's sea · Where to fish · Alerts · I'm back**.
3. **"Why?"** One sentence from `why.*`. "See all reasons" opens the ledger (Expert view).
4. **Instant acknowledgement:**
   - Within 1 s of releasing the mic button, play a short cached "checking the sea…" clip, then show the verdict.
   - Details follow below the verdict card.
5. **Trips + "I'm back" + family notice.**
   - A trip opens when a live position leaves the harbour geofence. It closes on re-entry or when the fisher taps **I'm back**.
   - On close, notify valid `share_grants` holders: "Appa is back at {harbour}, {time}".
6. **Feedback.** After close: 👍/👎 + optional voice note into `trips.feedback`. Simple mode shows "Right on N of the last M days". Thresholds change only by human review, never automatically.
7. **Alert budget:**
   - Critical alerts always go out: H1 warnings, border at 5 km / 2 km, NO-GO while at sea.
   - At most 3 non-critical alerts a day.
   - Quiet hours from `user_prefs` (default 21:00–03:30) apply to non-critical alerts.
   - The same rule for the same boat repeats at most once per 2 h.
8. **Voice onboarding (< 60 s):** harbour → boat type (3 picture buttons) → spoken consent + **Turn on alerts** (Google sign-in or QR, then the browser's location and notification prompts) → `consents`, `user_roles(fisher)`, `boats`, `push_subscriptions`. Keep the full written notice behind "Read full notice".
9. **Sunlight theme** default in Kadal Mitra and web Simple mode: white background, black text, contrast ≥ 7:1, verdict ≥ 40 px, body ≥ 18 px; icons always paired with words.

**Tables:**

```sql
create table user_prefs (
  user_id uuid primary key references auth.users(id) on delete cascade,
  mode text not null default 'simple' check (mode in ('simple','expert')),
  language text not null default 'ta-IN',
  brief_time time,
  quiet_from time not null default '21:00', quiet_to time not null default '03:30'
);
create table trips (
  id uuid primary key default gen_random_uuid(),
  boat_id uuid not null references boats(id) on delete cascade,
  departed_at timestamptz not null,
  returned_at timestamptz check (returned_at is null or returned_at > departed_at),
  closed_by text check (closed_by in ('geofence','button')),
  advice_answer_id uuid,
  advice_verdict text check (advice_verdict in ('GO','CAUTION','NO-GO')),
  feedback text check (feedback in ('right','wrong')),
  feedback_note text check (length(feedback_note) <= 500)
);
```

---

## 11. Expert mode (web)

- **Layout:** full MapLibre map; CopilotKit sidebar; Mission Control strip (behind a "Show how it works" toggle); departure slider.
- **deck.gl layers:** SST/chl heatmaps, PFZ polygons, IMBL/MPA/EEZ from PMTiles, route, boats.
- **CopilotKit frontend tools:** `flyTo`, `showLayer`, `drawRoute`, `setTime`, `openLedger(answerId)`, `openCitation(chunkId)`.
- **Cards:** Sea Signal + 24 h ribbon; Constraint Ledger open by default; citation chips (issuer · date · valid till).
- **Human-in-the-loop:** officer broadcasts and route sharing require approval.
- **Analyst tools:** anomaly charts, PFZ-vs-INCOIS overlap, CSV/NetCDF downloads, KB browser.

---

## 12. Auth, data, security

- **Supabase Auth.** Google sign-in only on web; staff are invited by email and sign in with Google. Fishers sign in with Google in Kadal Mitra (one tap on Android) or with the **Add this phone** QR shown by a signed-in family member or volunteer (`otp_expiry = 600`). TOTP `aal2` is mandatory for `analyst`, `officer`, `platform_admin`.
- **Roles:** enum `app_role` (`fisher`, `family`, `analyst`, `officer`, `platform_admin`) in `user_roles`, injected by `custom_access_token_hook` as claim `app_role`.
- **Token verification:** services verify JWTs with PyJWT `PyJWKClient` against `/auth/v1/.well-known/jwks.json` (ES256/RS256, `aud=authenticated`, issuer checked).
- **Tables:** `boats`, `positions` (geography Point, GiST + BRIN), `share_grants` (expiring), `consents` (per purpose, notice version, language), `alert_subscriptions`, `alerts`, `answers`, `feedback`, `push_subscriptions` (endpoint unique, p256dh, auth, last_ok_at; delete on 404/410), `user_prefs`, `trips`, `kb_documents`, `kb_chunks`, `audit_log` (append-only, hash-chained trigger), `ingest_runs`.
- **RLS on every table:**
  - owner-only by default;
  - family reads a boat only with an unexpired grant;
  - an officer reads positions only inside `active_warning_areas`, with `aal2`, for the last hour.
- **Request handling:** each request sets `request.jwt.claims` + `set local role authenticated`. The worker uses `ty_worker` (bypassrls, never web-reachable).
- **Retention:** raw positions 30 days, then aggregated to H3 without user id; alerts and audit log ≥ 1 year; answers and ledgers 180 days; voice audio not stored.
- **Security:**
  - Pydantic/Zod strict input; lat/lon must be inside the EEZ box.
  - Rate limits in Redis: anonymous 20/h/IP, signed-in 60/h.
  - Daily LLM spend cap.
  - Strict CORS and CSP; push payloads carry an alert id and short text only, never coordinates; the VAPID private key exists only in the worker's environment.
  - The OTel span processor drops tokens, phones, emails and coordinate pairs.
- **Regulatory (design):**
  - DPDP Act 2023 + Rules 2025: consent, erasure ≤ 90 days, breach runbook, adults only.
  - CERT-In 2022: 180-day logs, NTP, contact.
  - Geospatial Guidelines 2021: official India boundaries; label the IMBL source.
  - Fishing ban: H4.
  - INCOIS/IMD authority: H1 + footer.
  - GFW non-commercial licence.

---

## 13. Observability and admin console

**Telemetry:** OTel → `grafana/otel-lgtm` (Grafana on `127.0.0.1:3001`; OTLP on 4317/4318).

**Metrics:**

- `ty.answer.duration`, `ty.tool.duration`, `ty.tool.errors`
- `ty.cache.result{hit,miss,stale}`, `ty.feed.age_hours{source}`
- `ty.alerts.sent|failed`
- `gen_ai.client.*`, `ty.guardrail.events{type}`
- RAG no-answer rate
- **Daily-use measures:** briefs played, active days per fisher, trips closed, feedback rate, mutes

**`/admin` pages (MFA):**

- Overview
- Data sources (fetch now, pin snapshot)
- Knowledge base (quarantine approve/reject, re-index, Ragas scores, supersession chain, **Supersede with…**)
- Alerts (retry)
- AI usage (budget, force local)
- Guardrail review (blocked answers, dropped quotes; **Add to failures dataset**)
- **Replay** (an answer, or a boat + time: verdict, constraints, observations with `valid_at`/`known_at`, documents active then; export PDF)
- Users & roles
- Live map (anonymised)
- Audit log (verify hash chain)
- System health (Grafana panels)

Failed safety alerts also send a web push to every signed-in `platform_admin`.

**Provenance API:** `GET /sources/chunk/{id}` (public) and `GET /sources/answer/{id}` (owner token, or staff with `aal2`) on `ty-channels`, plus the MCP tool `sources`: document, issuer, version, validity, verbatim quote, topics, supersession chain.

**Harness rule — every failure becomes a permanent test.** Each wrong answer (team review, a fisher's 👎, Guardrail review) gets a row in `tests/failures/failures.yaml` (id, found, input, snapshot, wrong, cause, guard, expect). `make test` replays every row on its snapshot; promptfoo imports the LLM-facing rows. A fix is done only when its row passes.

---

## 14. Infrastructure, Docker and deployment

**Laptop.** Infra runs in `infra/docker-compose.yml`:

- `neo4j:5-community` (heap 512m, pagecache 256m)
- `redis:7-alpine` with password, 256 MB, `allkeys-lru`, AOF
- `grafana/otel-lgtm`

All ports are bound to `127.0.0.1`. Supabase runs via `pnpm supabase start -x imgproxy,edge-runtime,logflare,vector,supavisor`. Ollama runs natively (systemd) with `OLLAMA_CONTEXT_LENGTH=8192`. App processes run natively via `make dev`.

**`docker/Dockerfile.python`** (shared; Render passes env vars as build args):

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/      # pin a uv version tag before the final build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 ORCA_CONFIG_DIR=/app/config
ARG SERVICE_DIR
WORKDIR /app
COPY packages/ /packages/
COPY ${SERVICE_DIR}/pyproject.toml ${SERVICE_DIR}/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY ${SERVICE_DIR}/ ./
COPY config/ /app/config/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
RUN useradd --create-home --uid 10001 ty && chown -R ty:ty /app
USER ty
ENV PATH="/app/.venv/bin:$PATH"
```

**`docker/Dockerfile.embed`:**

```dockerfile
FROM ollama/ollama:latest
ENV OLLAMA_HOST=0.0.0.0:11434
RUN ollama serve & sleep 5 && ollama pull bge-m3
```

**Showcase (`render.yaml`, region `singapore`).** Copy the full file from the specification, Section 15.2 "Tier 1".

| Resource | Type | Plan | Notes |
|---|---|---|---|
| `ty-agent` | web | `0.5c-512mb` | `/bin/sh -c "langgraph dev --host 0.0.0.0 --port $PORT --no-browser --no-reload"`, health `/ok` |
| `ty-channels` | web | `0.5c-512mb` | uvicorn on `$PORT`, health `/health` |
| `ty-mcp` | private service | `1c-2g` | — |
| `ty-embed` | private service | `1c-2g` | `Dockerfile.embed` |
| `ty-watch` | cron | `0.5c-512mb` | `*/15 * * * *`, `python -m ty_worker.watch_once` — includes briefs, trips, alert budget |
| `ty-ingest` | cron | `0.5c-512mb` | `30 20 * * *`, `python -m ty_worker.ingest_once` |
| `ty-cache` | Key Value | `free` | `ipAllowList: []`, `allkeys-lru` |

Other showcase settings:

- **Env groups:** `ty-settings` (in YAML: `DATA_MODE=snapshot`, `RERANK_MODEL=none`, `LLM_MODE=cloud`, …) and `ty-secrets` (created in the dashboard). Services get `*_HOSTPORT` via `fromService`.
- **Knowledge base:** the laptop indexes it for the showcase with `make kb-index TARGET=showcase`.
- **Web:** Vercel with `{"regions": ["sin1"]}`; `LANGGRAPH_DEPLOYMENT_URL=https://ty-agent.onrender.com`.
- **Push:** separate VAPID key pairs for the laptop and the showcase; Vercel gets `NEXT_PUBLIC_VAPID_PUBLIC_KEY` and `NEXT_PUBLIC_CHANNELS_URL=https://ty-channels.onrender.com`.
- **Phone on the laptop:** `make tunnel` (cloudflared quick tunnel to :3000; push and service workers need HTTPS). `next.config.ts` rewrites `/sb/*` → `127.0.0.1:54321` and `/ch/*` → `127.0.0.1:8002`; browser clients use `${location.origin}/sb` and `/ch` when `NEXT_PUBLIC_SAME_ORIGIN_PROXY=1`.

---

## 14a. Android app — Kadal Mitra (Milestone 11, pilot stage only)

Build only when the pilot needs **background geofencing** (alerts with the screen off, the app closed and no network) or **offline trip maps**. Until then, the Kadal Mitra PWA with web push is the mobile experience. Full design: specification Chapter 17.

**Stack (exact):**

- **Framework:** Expo SDK 57 (RN 0.86) + TypeScript + `expo-router`, run as a **development build** (`expo-dev-client`); Expo Go cannot run background location or MapLibre.
- **Maps:** `@maplibre/maplibre-react-native` v11 (`Map`, new architecture) with **local PMTiles** (`pmtiles://file://…`; MapLibre Android ≥ 11.7.0). Do **not** use `OfflineManager` packs with PMTiles.
- **Location:** `expo-location` + `expo-task-manager`.
- **Device services:** `expo-notifications`, `expo-sqlite`, `expo-file-system`, `expo-audio`.
- **Geometry:** Turf (`@turf/point-to-line-distance`, `@turf/boolean-point-in-polygon`).
- **Auth:** `@supabase/supabase-js` with AsyncStorage + `react-native-url-polyfill`; Google sign-in via `@react-native-google-signin/google-signin` → `signInWithIdToken`.
- **Agent:** `@copilotkit/react-native/headless` + `react-native-get-random-values` + `zod`.
- **Data fetching:** TanStack Query.

**Background flow:**

1. **Harbour geofence:** register `startGeofencingAsync("ty-harbour", [{ identifier: "home", latitude, longitude, radius: 1500 }])` at onboarding.
2. **Exit → trip mode:** `startLocationUpdatesAsync("ty-trip", { accuracy: Balanced, timeInterval: 60000, distanceInterval: 100, foregroundService: {...} })`.
3. **Each fix:**
   - Turf distance to the bundled IMBL line → local alert at 5 km (warning) and 2 km (alarm).
   - MPA and cached warning polygons → local alert.
   - Append the fix to the SQLite outbox; sync to `ty-channels /positions` when online.
4. **Enter → stop trip mode:** close the trip, ask 👍/👎; the server notifies the family on sync.
5. Define both tasks with `TaskManager.defineTask` at module top level and import them from the root layout.

**Config (`app.config.ts`):**

- Plugins: `expo-router`, `@maplibre/maplibre-react-native`, `expo-notifications`, `expo-sqlite`.
- `expo-location` with `isAndroidBackgroundLocationEnabled: true`, `isAndroidForegroundServiceEnabled: true` and a permission string explaining border safety.
- `expo-build-properties` with `usesCleartextTraffic: true` **only when `APP_ENV=development`**.

**Permissions:** foreground → full-screen Tamil/English explanation → background. Background location needs a Google Play declaration.

**Offline maps:**

- Build `gom_basemap.pmtiles` with `pmtiles extract <protomaps build> gom_basemap.pmtiles --bbox=78.0,8.0,80.5,10.5 --maxzoom=12`, plus the layer PMTiles, into the public Supabase Storage bucket `mobile-maps` with a SHA-256 manifest.
- The app downloads them once on Wi-Fi, verifies the hashes, and writes a local style JSON.
- The trip pack (verdict ribbon, PFZ GeoJSON, warning polygons, route, phrase text + TTS audio) is saved to SQLite at brief time and at harbour exit.

**CopilotKit RN:**

- **Entry imports, first:** `import "react-native-get-random-values"; import "@copilotkit/react-native/polyfills";`.
- **Provider:** `<CopilotKitProvider runtimeUrl={`${EXPO_PUBLIC_WEB_URL}/api/copilotkit`} headers={{ Authorization: `Bearer ${jwt}` }} properties={{ mode: "simple", lang }}>` — the same runtime route as the web app.
- **Chat:** `useAgent({ agentId: "default" })` + `useCopilotKit().runAgent({ agent })` with a custom `FlatList` UI.
- **Frontend tools:** `useFrontendTool` with zod for `flyTo` and `openWhy`.
- **Voice:** `expo-audio` → `ty-channels /stt` (Sarvam); replies play from the `tts` cache URL.
- **Server pushes:** `getExpoPushTokenAsync` → `POST /push/subscribe` with `kind: "expo"` (`push_subscriptions.kind in ('web','expo')`). The **same worker** sends them: `httpx` POST to `https://exp.host/--/api/v2/push/send` with `EXPO_ACCESS_TOKEN`, after the alert budget and quiet-hour checks. Do not use Supabase database webhooks + Edge Functions for push.
- **Metro:** `metro.config.js` from `expo/metro-config` plus the documented `resolveRequest` override that resolves only `jose` with the `browser` condition.

**Screens (Simple mode only):** Today · Map · Trip · Alerts · Me. Expert mode stays on the web.

**Simulation:** Android Emulator (Android Studio on Windows, API 34 Google APIs x86_64).

- `scripts/sim_boat.py --gpx` exports the boat track.
- Load it under **Extended controls → Location → Routes** for demos.
- For repeatable tests, `scripts/replay_gpx.py` sends `adb emu geo fix <lon> <lat>` per point (run with Windows Python).
- The emulator reaches WSL services at `10.0.2.2` (Metro :8081, web :3000).

**Builds:** `eas.json` profiles: `development` (`developmentClient: true`, internal), `preview` (APK, internal), `production`. Use `eas build --profile development|preview --platform android`, and `adb install` on the emulator.

## 15. Milestones (one PR each; stop and summarise after each)

| # | Milestone | Acceptance criteria |
|---|---|---|
| 1 | Scaffold | Starter cloned, `apps/web` renamed; uv packages (`tarangyukti`, `ty-channels`, `ty-worker`, `ty-common`) with editable `ty-common`; `ty_common.cache` (`@cached`, `fingerprint`, `invalidate`) with its tests; settings modules; `.env.example`; `infra/docker-compose.yml` healthy; Supabase local with `vector` + `postgis`; Makefile `dev`; CI (ruff, mypy, pytest, eslint, tsc, build) green |
| 2 | Data tools + cache + snapshots | `ToolResult` for marine_forecast, imd_warnings (snapshot fixture), incois_alerts, pfz_incois, sst_grid, chl_grid, fence_check, geo_distance; all tools wrapped with `@cached(ns="tool")`; `snapshots` bucket migration; `make snapshot`; `DATA_MODE=snapshot` works offline; unit + tool + cache tests |
| 3 | Yukti engine + route | H1–H8, S1–S5 from YAML; outcome mapping; earliest-window search; time-expanded A*; Neo4j ledger write; Hypothesis property tests (a new warning never makes a trip safer; tightening a limit never adds windows; every refusal has a failed hard constraint) |
| 4 | RAG | `kb_*` migrations + `kb_hybrid_search`; Docling ingest with sanitiser + versioning + cross-document supersession; `config/aliases.yaml` + `kb_chunks.topics`; `known_at` replay in `kb_hybrid_search`; bge-m3 + reranker; `kb_search` tool; golden set + `make eval-rag` gates met |
| 5 | Agent graph | Planner + 8 specialists; validator (numbers, citations, **verbatim quotes**, language); locked ledger schema with `valid_at`/`known_at`; `tests/failures/failures.yaml` harness wired into `make test`; fallback chain Gemini → qwen3.5:4b → template; OTel traces visible in Grafana |
| 6 | Simple mode + Kadal Mitra PWA | Manifest + `public/sw.js` (push, notificationclick, offline brief); `/push/subscribe` + `push_subscriptions`; pywebpush sender + `make push-test`; `make tunnel` + `/sb` `/ch` rewrites; Phrases files; Sarvam STT/TTS (MediaRecorder → `/stt`, `/tts` mp3); instant acknowledgement; four buttons; "Why?"; voice onboarding + consent + Add-this-phone QR; **morning brief** + `make brief-now`; Simple web home with sunlight theme; Simple replies contain no codes (test) |
| 7 | Expert console | Map + layers + CopilotKit frontend tools; Sea Signal + ribbon; ledger; citations; departure slider; Mission Control toggle; analyst tools; Playwright hero flow |
| 8 | Alerts, trips, family, feedback | `watchPosition` while open (every 60 s) + `sim_boat.py` → `positions`; geofence 5 km / 2 km; trips open/close by geofence and button; family notice; feedback; alert budget + quiet hours; frozen-clock tests |
| 9 | Auth, RLS, admin | Google sign-in; roles hook; MFA for staff; RLS on every table with cross-user tests; My data download/delete; audit chain + verify; `/admin` pages incl. daily-use measures, **Replay** and Guardrail review → failures dataset; `GET /sources/{kind}/{id}` |
| 10 | Showcase + docs | `docker/` files; `render.yaml`; Render + Vercel + Supabase Mumbai + AuraDB live; showcase VAPID pair + test push to an installed phone; `scripts/demo.sh` + `smoke.sh` green from cold boot; README, THIRD_PARTY.md, eval and test reports |
| 11 | Android app (pilot stage only — start when background geofencing or offline trip maps are required) | Gates M-G1…M-G5 from specification Section 17.11: dev build + Google sign-in + live verdict; screen-locked GPX replay raises 5 km / 2 km alerts and harbour exit/enter toggles trip mode; airplane mode keeps map, route, border line, brief and alerts working and the outbox syncs later; Tamil CopilotKit chat drives `flyTo`/`openWhy` with audio replies; preview APK used by two pilot phones for a week |

---

## 16. Testing requirements

| Layer | What to test |
|---|---|
| Unit | Distances, geofence rings, risk levels, ban calendar, QC ranges, H3 keying, phrase slot filling |
| Property | The Yukti invariants in Milestone 3; route never enters removed cells or bad-weather time steps |
| Tool contract | Every tool online (respx-mocked), cached, stale, snapshot |
| Cache | L1/L2 hit; new source version → new key; config change → new keys; 200 concurrent calls → 1 computation; stale-if-error; tag invalidation clears L1 in other processes; `CACHE_DISABLED=1` gives same answers; E2E scan finds no phone, email or lat/lon in any cached value (fakeredis) |
| RAG | Expired advisory never returned; superseded advisory hidden after `superseded_at` but returned for an earlier `known_at`; region filter; `simple` FTS matches Tamil; RRF merge; eval gates |
| Provenance | Paraphrased/stitched quotes rejected, exact spans (whitespace/NFKC variants) accepted; every alias → one slug; `/sources/answer/{id}` refuses other users; replay reproduces a past ledger from its snapshot |
| Failures dataset | Every row of `tests/failures/failures.yaml` passes; removing a row fails CI |
| Grounding | Invented "2.7 m" rejected; times like 05:30 handled; fake `[K9]` removed; language mismatch caught |
| Daily-use | Brief once, 30 min before learned departure; quiet hours; ≤ 3 non-critical alerts a day; trip open/close; one family notice |
| Security | RLS isolation; officer `aal2` + warning-area rule; missing token → 401; another user's push subscription unreadable; 410 from the push service deletes the subscription; out-of-EEZ input rejected; audit tamper detected |
| LLM safety | promptfoo: injection inside a bulletin changes nothing; out-of-coverage refusal; Tamil in → Tamil out; no ungrounded numbers |
| Mobile (M11) | Jest: Turf distance within 50 m of PostGIS on fixtures; on-device alert budget; emulator GPX replay with screen locked and in airplane mode |
| E2E | Playwright: public Simple verdict → Why? → Expert → ledger → login → save boat → share with family → admin audit shows events |

CI runs everything except GPU/LLM-live tests (`-m "not gpu and not llm"`). Run those on the laptop with `make test-local` and commit the report.

---

## 17. Coding conventions

- **Python:** ruff + `mypy --strict` on services; async I/O; `httpx.AsyncClient` with timeouts; no bare `except`; structured JSON logs with request id.
- **TypeScript:** strict; Zod for all external data; server components by default, client components only for the map, CopilotKit and interactive cards.
- **Time:** stored UTC, displayed IST.
- **Prompts and phrases:** in files, never inline strings.
- **Tool docstrings:** state units and limits (the LLM reads them).
- **Hygiene:** comment only non-obvious logic; leave `TODO(tarangyukti):` with the assumption when unsure.

---

## 18. Do NOT

- Let the LLM produce numbers or safety sentences that are not from tools or approved phrases.
- Show codes (PFZ, IMBL, H1–H8), Mission Control or sliders in Simple mode.
- Send more than 3 non-critical alerts a day, or anything non-critical during quiet hours.
- Cache free-text LLM replies or personal data; use pickle anywhere; write a second cache implementation instead of `ty_common.cache`; create vector indexes in Neo4j.
- Use LangSmith, Chainlit, Streamlit, Railway or `langgraph-supervisor`.
- Run the agent or the geospatial stack as Vercel Functions.
- Start the Android app before Milestone 11's trigger, use Expo Go for it, use MapLibre `OfflineManager` packs with PMTiles, or ship cleartext HTTP in non-development builds.
- Expose `SUPABASE_SERVICE_ROLE_KEY`, `REDIS_URL` or any secret to the browser or bake it into an image.
- Add Memgraph, Graphiti, Inngest, LLM claim/entity extraction into a graph, Kubernetes or Langfuse in the prototype; let an LLM write Cypher or invent ledger labels; translate or paraphrase a `quote`.
- Add Telegram, WhatsApp or any chat bot in the prototype; put the VAPID private key in the web app; ask for notification permission before the user taps **Turn on alerts**; put coordinates in a push payload.
- Hard-code thresholds, phrases, keys or real user coordinates.
- Contradict an active official warning, or say "safe" without "advisory only".
- Add features outside the current milestone without asking.

---

## 19. When unsure

Pick the simplest option that keeps Section 2. Leave a `TODO(tarangyukti):` explaining the assumption, and list every assumption in the PR description. If a library's current API differs from this file, follow its current documentation and note the difference in the PR. For anything not covered here, follow `docs/TarangYukti_Engineering_Specification_v2.0.md`.
