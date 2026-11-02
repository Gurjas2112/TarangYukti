# TarangYukti — Build Prompt for GitHub Copilot (coding agent)

> **How to use this file**
> - Save it twice in the repo: `.github/copilot-instructions.md` (Copilot reads it on every request) and `AGENTS.md` at the root (Copilot coding agent, Cursor, Claude Code and others read it).
> - Keep `docs/TarangYukti_Engineering_Specification_v2.2.md` in the repo. This prompt is the build contract; the specification has the reasoning, diagrams and full detail. **If the two disagree, the specification wins.**
> - Assign **one milestone per issue / pull request**, e.g. *"Implement Milestone 3 from AGENTS.md"*. Never attempt the whole system in one task.
> - This file replaces `ORCA_COPILOT_PROMPT.md`.
> - **Solo build:** one person owns every role. Follow the build order and solo substitutes of specification Annexure I (required checks + `safety-hold` 24-hour wait instead of a second reviewer; external reviewers still required for languages and the security audit).

---

## 1. Role and goal

You are a senior full-stack engineer building **TarangYukti** (तरंग *wave* + युक्ति *reasoning*): a constraint-reasoning marine copilot over ISRO/INCOIS ocean data. It is a prototype for **Smart India Hackathon 2026, ISRO problem statement 26176 — "ORCA: Marine EcOsystem Reasoning with Collaborative Agents"**.

Users ask in any of the 22 scheduled Indian languages or English, by voice or text: *"Can I go to sea tomorrow morning?"*, *"Where is the nearest fishing zone?"*, *"Why has catch dropped here?"*. TarangYukti answers in the same language and gives a verdict with its reasons. It also **pushes** a morning brief before departure, warns near the India–Sri Lanka border line (IMBL) and protected areas, and tells the family when the boat is back.

**Prototype scope — do not exceed:**

- **Region:** Gulf of Mannar + Palk Bay only (bbox lon 78.0–80.5, lat 8.0–10.5; home harbour Rameswaram 9.288 N, 79.313 E).
- **Languages:** **all 22 scheduled languages + English — no language is built in** (specification Section 6.5). Every string, phrase, voice, alias, golden-set question, walkthrough and video narration is a per-language file; a language is shown to real users once `config/languages.yaml` marks it `released` (two native-speaker reviewers, gates green). Group A (voice in and out): Hindi, Bengali, Marathi, Telugu, Tamil, Gujarati, Kannada, Malayalam, Odia, Punjabi, English. Group B (voice in, text out): Konkani, Urdu, Assamese, Nepali, Kashmiri, Sindhi, Santali, Manipuri, Bodo, Maithili, Dogri, Sanskrit. Onboarding suggests the harbour state's language (Table 6-12) and accepts any other. Never hard-code a default language: use `user_prefs.language`, else the nearest released language to the device locale.
- **Client:** **one Expo (React Native) app**, `apps/app`, built for **Android** (Kadal Mitra for fishers: background border alerts, offline trip maps, Expo push) and the **web** (Expert, analyst, officer and admin screens; families on desktops; iPhone users). No Next.js, no native iOS build, no Telegram or any chat bot.
- **Primary run target:** a single Windows 11 laptop (WSL2 Ubuntu 22.04, i7-11800H, 16 GB RAM; the RTX 3060 is optional and only speeds up Docling). **No model runs locally.** The demo must work **offline** for buttons, map, alerts and document search; free-form chat and voice need the network.
- **Tier 1 — live testing with real users:** pay-as-you-go **Azure Container Apps, Central India**, zone-redundant in a VNet, every app ≥ 2 replicas, behind **Front Door Standard + WAF**; Application Insights with on-call alerts; Azure Load Testing gate; Supabase **Pro** (Mumbai) + Neo4j **AuraDB Professional**. Scale-out target: AKS (not in the prototype).

---

## 2. Non-negotiable rules

1. **The LLM never produces a number.** Every wave height, distance, time, coordinate and temperature in a reply comes from a tool result carrying `source` and `fetched_at`. A validator rejects replies with ungrounded numbers.
2. **Constraints decide; the LLM explains.** Go / Caution / No-Go comes from the deterministic Yukti constraint engine. Every refusal names its constraint (e.g. `H2`) and evidence.
3. **Official warnings win; never say "safe".** An active INCOIS/IMD warning forces NO-GO. The best verdict is "GO — no constraint violated, advisory only". Every answer ends with "Advisory only — follow official INCOIS/IMD warnings."
4. **Same language in and out.** The user's language comes from `user_prefs.language` (picked at onboarding) or the device locale; detection (Sarvam `text-lid`, Saaras transcript) may only switch between released languages it can identify. Store it in thread state; reply and render the interface in it.
5. **Simple mode by default.** Fishers, families and the public get plain words, a verdict card and four buttons. Codes (PFZ, IMBL, H1–H8), the ledger, Mission Control and sliders appear only in Expert mode.
6. **Safety wording comes from approved phrases.** Simple-mode replies fill slots in `config/phrases/<code>.yaml` of a **released** language (`status: approved`, two native-speaker reviewers). Never let the LLM or machine translation produce a safety sentence.
7. **Public answers need no login.** Login is only for personal features (boats, live location, family sharing, alert subscriptions) and staff roles.
8. **Personal data stays in Supabase Postgres under RLS.** Never put phone numbers, names or raw coordinates in Redis, Neo4j, logs or traces. Caches key by H3 cell.
9. **Snapshot mode always works.** `DATA_MODE=snapshot` reads the dated snapshot from the Supabase Storage bucket `snapshots`, so the demo runs without data-source APIs.
10. **Small, typed, tested.** Python 3.12 with type hints and Pydantic v2 strict models. TypeScript strict with Zod. Every milestone ships with tests.

---

## 3. Fixed tech stack (use exactly these)

| Layer | Pick |
|---|---|
| Monorepo base | Clone `https://github.com/CopilotKit/with-langgraph-python`; keep `apps/agent`, **delete its Next.js `apps/app`**, then `npx create-expo-app@latest apps/app --template default@sdk-57`; `.npmrc` `node-linker=hoisted` |
| Python packaging | `uv` (one `pyproject.toml` + `uv.lock` per service) |
| Agents | LangGraph 1.x + LangChain 1.x `create_agent`; supervisor via **tool-calling** (sub-agents wrapped as `@tool`); **not** `langgraph-supervisor` |
| Agent server + memory | **`apps/agent/server.py`**: FastAPI + `ag-ui-langgraph` (`LangGraphAGUIAgent` from `copilotkit`, own `POST /agent` route that streams `agent.run(...)` through `ag_ui.encoder.EventEncoder`), `GET /ok`; thread memory in Postgres via LangGraph **`AsyncPostgresSaver`** (`langgraph-checkpoint-postgres`, `psycopg_pool.AsyncConnectionPool` with `autocommit=True`, `prepare_threshold=0`, `row_factory=dict_row`, `search_path=agent`), role `ty_agent`. **Never run `langgraph dev` in Tier 1** (in-memory threads, lost across replicas and restarts); the self-hosted LangGraph Agent Server needs an enterprise licence — not used |
| LLM | **Cloud only.** Gemini via `langchain-google-genai`, model from `ORCA_MODEL` (default `gemini-3.8-flash`), `temperature=0`; **higher reasoning effort** for the planner and "why has catch dropped?", **low** for rewrites and routine explanations. Fallback after `LLM_TIMEOUT_S` or an API error: button flows render **templates from the ledger**; free-form questions say they need the network. No local model, no Ollama |
| Tools | FastMCP servers (streamable HTTP); agents connect with `langchain-mcp-adapters` `MultiServerMCPClient` |
| Reasoning | Yukti constraint engine (custom Python, Section 6) + time-expanded A* on H3 |
| RAG | Docling + HybridChunker → **Gemini Embedding 2** (`gemini-embedding-2`, `output_dimensionality=768`; prefixes `title: … \| text: …` for documents and `task: search result \| query: …` for queries; Batch API for bulk indexing) → Postgres pgvector HNSW + full-text (`simple` config) + PostGIS filters → RRF → top 8. **No reranker** |
| Speech and translation | Sarvam `sarvamai`: STT `saaras:v4` (mode `codemix`, keyterms; 23 languages), TTS `bulbul:v3` (`mp3`; 11 languages), **`sarvam-translate:v1`** (23 languages, formal, **international numerals**, ≤ 2,000 characters per request — split at sentence boundaries), `text-lid` (11 languages) |
| Localisation | **i18next + react-i18next + `expo-localization`**; strings in `apps/app/src/i18n/<code>.json` for Simple and Expert mode; **Noto** fonts per script bundled with `expo-font` (incl. Ol Chiki, Meetei Mayek, Nastaliq/Naskh); **right-to-left** for Urdu, Kashmiri, Sindhi (`I18nManager.forceRTL` + reload on Android, `dir="rtl"` on web; numbers, times and the map stay left-to-right) |
| Push | One sender, the worker: **Expo push** (`httpx` → `https://exp.host/--/api/v2/push/send`, `EXPO_ACCESS_TOKEN`) for Android and **pywebpush** (VAPID) for the web build; `push_subscriptions.kind in ('web','expo')`. Web build: hand-written `apps/app/public/sw.js` + `public/manifest.json` |
| Client app | **Expo SDK 57 + Expo Router** (React Native 0.86, TypeScript), targets `android` + `web` (`web.output: "single"`); platform files `*.native.tsx` / `*.web.tsx`; maps: `@maplibre/maplibre-react-native` v11 (Android) and MapLibre GL JS + deck.gl + `pmtiles` (web) behind one `OceanMap` contract; **`StyleSheet` + typed tokens** (no NativeWind); Recharts in web-only files; TanStack Query; Zod; `@copilotkit/react-native/headless` |
| Copilot runtime | **`services/copilot`** (`ty-copilot`): `@copilotkit/runtime` v2 on Node 24 — `CopilotRuntime({ agents: { default: new HttpAgent({ url: `${AGENT_URL}/agent` }) } })` with `HttpAgent` from `@ag-ui/client` (the version `@copilotkit/runtime` depends on); the runtime forwards the app's `Authorization` header to the agent served by `createCopilotNodeListener({ runtime, basePath: "/api/copilotkit", cors: true })` on `node:http`, port 8200 |
| Auth / DB / files | Supabase: Auth (**Google sign-in only**, also on the phone; "Add this phone" QR = one-time `token_hash` from `auth.admin.generate_link` verified with `verifyOtp`; TOTP MFA for staff), Postgres 17 + PostGIS + pgvector, RLS, Storage |
| Evidence graph | Neo4j 5 (local container; AuraDB Professional in Tier 1) — Constraint Ledger only. **Never create vector indexes in Neo4j** |
| Cache | **`ty_common.cache`** — one two-tier cache for every service: L1 **cachetools** `TTLCache` in-process + L2 **Redis 7** via `redis.asyncio` (local container; `ty-redis` internal container app in Tier 1) + **orjson**. JSON only, never pickle (Section 7a) |
| Geo / science | xarray, netCDF4, copernicusmarine, GeoPandas, Shapely, h3 (v4), NetworkX, scikit-image, pyarrow |
| Scheduling | APScheduler in one `worker` process locally; **Container Apps scheduled jobs** in Tier 1 (same run-once functions; cron in UTC) |
| Observability | OpenTelemetry → `grafana/otel-lgtm` container on the laptop; in Tier 1 the same instrumentation exports to **Application Insights** via `azure-monitor-opentelemetry` (`configure_azure_monitor()`, Python) and `@azure/monitor-opentelemetry` (Node) when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set; `openinference-instrumentation-langchain`. **No LangSmith** |
| Agent improvement | **TraceRoot** (specification Section 10.4) on **test traffic only**: `traceroot` (Python) with `traceroot.initialize(integrations=[Integration.LANGCHAIN, Integration.GOOGLE_GENAI])`, `using_attributes`, `update_current_trace`, `@observe(type="tool")`; `@traceroot-ai/traceroot` (TypeScript) `TraceRoot.initialize()` + `observe(...)` in `ty-copilot`; `traceroot-cli`. TraceRoot Cloud Free plan; enabled only when `TRACEROOT_ENABLED=true` and `ENV` is not `live` |
| Quality | pytest, pytest-asyncio, Hypothesis, respx, fakeredis, Schemathesis, Jest (`jest-expo`), Playwright (web build), Android Emulator + GPX, Ragas, promptfoo, Ruff, mypy, ESLint, `tsc --noEmit`, `az bicep build`, **Locust** on **Azure Load Testing** |
| Hosting | Laptop: native processes in WSL + Docker Engine (not Docker Desktop) for infra. Tier 1: **Azure Container Apps, `centralindia`**, from `infra/azure/{main,app,job,edge,monitor}.bicep`, deployed by `.github/workflows/deploy-azure.yml` (OIDC, `az acr build`, GitHub environment `live` with required reviewer, smoke test through Front Door) after CI passes |

---

## 4. Repository layout (create exactly this)

```
tarangyukti/
├── apps/
│   ├── app/                      # Expo SDK 57 + Expo Router — Android + web (one codebase)
│   │   ├── app/(simple)/         # Today · Map · Trip · Alerts · Me (both targets)
│   │   ├── app/family/           # shared boat card
│   │   ├── app/expert/ · analyst/ · officer/ · admin/   # *.web.tsx + non-platform "open on a computer" fallback
│   │   ├── app/_layout.tsx       # polyfills first, CopilotKitProvider, background task registration
│   │   ├── src/map/              # types.ts (OceanMap contract), OceanMap.native.tsx, OceanMap.web.tsx
│   │   ├── src/tasks/            # trip.native.ts (ty-harbour, ty-trip), trip.ts (web stub)
│   │   ├── src/components/       # VerdictCard, FourButtons, WhySheet, TimeRibbon, ConstraintLedger,
│   │   │                         # CitationChip, MissionControl, DepartSlider
│   │   ├── src/ui/tokens.ts · src/copilot/ · src/offline/ · src/auth/ · src/i18n/<code>.json · assets/fonts/
│   │   ├── public/               # sw.js, manifest.json, icons (web build only)
│   │   ├── e2e/maestro/ · promptfoo/ · app.config.ts · eas.json · metro.config.js
│   │   └── package.json          # name "@repo/app"
│   └── agent/                    # LangGraph
│       ├── main.py               # async make_graph(checkpointer) -> compiled graph
│       ├── server.py             # FastAPI AG-UI endpoint /agent, /ok; AsyncPostgresSaver lifespan
│       ├── src/agents/           # language, planner, discovery, weather, ocean, geo, knowledge, yukti, explain
│       ├── src/prompts/          # one .md per agent; planner prompt first and stable (≥ 4,096 tokens incl. tool schemas)
│       ├── src/validator.py
│       └── langgraph.json        # LangGraph Studio debugging only; never deployed
├── services/
│   ├── mcp/                      # uv package name "tarangyukti" (avoids clashing with the `mcp` library)
│   │   └── src/tarangyukti/{server.py, cache.py, tools/, yukti/, route.py, rag/, qc.py, phrases.py}
│   ├── channels/                 # package "ty-channels": voice/device API — /stt, /tts, /positions, /push/subscribe, /trips, /phone-link
│   ├── worker/                   # package "ty-worker": ingest, kb_index, watch (brief, trips, alerts), push (Expo + web)
│   │   └── src/ty_worker/{__main__.py, ingest_once.py, kb_index.py, watch_once.py, push.py}
│   └── copilot/                  # ty-copilot: src/server.ts, package.json, package-lock.json (Node 24)
├── packages/ty-common/           # auth (JWKS), settings, OTel setup, ToolResult, cache (@cached), edge.py (Front Door check); editable path dependency
├── supabase/                     # config.toml, migrations/, seed.sql
├── infra/docker-compose.yml      # neo4j, redis, otel-lgtm (laptop)
├── infra/azure/                  # main.bicep, app.bicep, job.bicep, edge.bicep, monitor.bicep (Tier 1)
├── docker/                       # Dockerfile.python, Dockerfile.copilot, Dockerfile.web (nginx, SPA fallback)
├── tests/                        # failures/failures.yaml · load/dawn_rush.py (Locust, Gate L1)
├── config/                       # constraints.yaml, boats.yaml, qc.yaml, sources.yaml, languages.yaml, phrases/<code>.yaml (23)
├── kb/sources/                   # allow-listed document manifests
├── ops/grafana/                  # dashboards + alert rules
├── scripts/                      # demo.sh, smoke.sh, db_roles.sh, sim_boat.py, sim_warning.py, replay_gpx.py, grafana_provision.sh, capture_walkthrough.sh
├── video/                        # Remotion story video: script/, scripts/build_assets.py, src/scenes/, src/components/
├── .claude/                      # settings.json, commands/walkthrough.md
├── artifacts/                    # git-ignored: APKs, app-walkthrough/<version>-<date>-<lang>/
├── docs/                         # specification, eval-report.md, test-report.md, incident-runbook.md, go-live.md, dpia.md, governance.md, releases.md
├── Makefile · README.md · THIRD_PARTY.md · .env.example · .npmrc · AGENTS.md
└── .github/{copilot-instructions.md, CODEOWNERS, workflows/ci.yml, workflows/deploy-azure.yml, workflows/android-release.yml}
```

---

## 5. Environment variables (`.env.example`)

```dotenv
ENV=local
# Supabase
SUPABASE_URL=http://127.0.0.1:54321
DATABASE_URL=postgresql://ty_api:<password>@127.0.0.1:54322/postgres          # no BYPASSRLS
WORKER_DATABASE_URL=postgresql://ty_worker:<password>@127.0.0.1:54322/postgres
AGENT_DATABASE_URL=postgresql://ty_agent:<password>@127.0.0.1:54322/postgres    # schema agent only (thread memory)
SUPABASE_SERVICE_ROLE_KEY=                                                     # channels + worker only
# LLM
GOOGLE_API_KEY=
ORCA_MODEL=gemini-3.8-flash
LLM_TIMEOUT_S=20                       # then button flows answer from templates
# RAG
EMBED_MODEL=gemini-embedding-2
EMBED_DIM=768
RAG_MIN_SIM=0.55                       # best cosine similarity below this = "nothing relevant"; calibrate on the golden set
# Speech, push
SARVAM_API_KEY=
VAPID_PUBLIC_KEY=                      # npx web-push generate-vapid-keys --json; same value as EXPO_PUBLIC_VAPID_PUBLIC_KEY
EXPO_ACCESS_TOKEN=                     # expo.dev access token with enhanced push security; worker only
VAPID_PRIVATE_KEY=                     # worker only, never in the browser
VAPID_SUBJECT=mailto:
# Data
DATA_MODE=online                       # demo.sh sets snapshot on demo day; Tier 1 runs online
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
MCP_URL=http://127.0.0.1:8001/mcp      # Azure: http://ty-mcp/mcp (app name, same environment)
AGENT_URL=http://127.0.0.1:8123        # Azure: http://ty-agent
WEB_ORIGIN=http://localhost:8081       # Azure: https://<Front Door web endpoint host> (set by Bicep)
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
# Agent improvement loop — test traffic only, never Tier 1
TRACEROOT_ENABLED=false
TRACEROOT_API_KEY=
TRACEROOT_HOST_URL=https://app.traceroot.ai
TRACEROOT_ENVIRONMENT=local-eval
TRACEROOT_USER_SALT=
# Tier 1 only (set by Bicep)
FRONTDOOR_ID=                          # public apps reject requests whose X-Azure-FDID differs (health paths exempt)
APPLICATIONINSIGHTS_CONNECTION_STRING=
```

Read config through one settings module per service: `pydantic-settings` in `ty-common`, a Zod-validated `src/env.ts` in the app reading only `EXPO_PUBLIC_*` (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `COPILOT_URL`, `CHANNELS_URL`, `VAPID_PUBLIC_KEY`, `GOOGLE_WEB_CLIENT_ID`) — these are public and compiled into the app; never put a secret there. Never commit real values.

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
| `kb` | Hybrid search result | query hash, H3 cell, hour, `index_version` | 10 min |
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
- **Ingest (`kb_index`):** fetch → SHA-256 skip if unchanged → sanitise (quarantine injection-like text) → Docling → HybridChunker (≤ 512 tokens) → metadata (issuer, doc_type, language, `valid_from/valid_to`, region polygon) → Gemini Embedding 2 (768-d, document prefix) → upsert; old versions become `superseded`, never deleted while cited; bump `index_version`.
- **Schema:** `kb_documents` (source_id, version, issuer, doc_type, language, url, licence, sha256 unique, valid_from, valid_to, region geography, status, `ingested_at`, `superseded_by` → kb_documents, `superseded_at`; check: status 'superseded' ⇔ superseded_at set) and `kb_chunks` (document_id, ord, heading_path, content, `fts tsvector generated always as (to_tsvector('simple', content)) stored`, `embedding vector(768)`, embed_model default `'gemini-embedding-2'`, index_version, `topics text[]` canonical slugs) with HNSW cosine + GIN (fts, topics) + GiST indexes.
- **Supersession across documents:** a newer INCOIS/IMD bulletin or a corrigendum replaces an older one via a parser rule in `config/sources.yaml` or the admin **Supersede with…** action; both set `superseded_by` + `superseded_at`.
- **Query:** `kb_hybrid_search(q_text, q_emb, at, near, k=40, rrf_k=50, known_at=now())` SQL function:
  - filters `status <> 'quarantined'`, `ingested_at <= known_at`, `superseded_at is null or > known_at`, validity at `at`, `ST_DWithin(region, near, 50000)` (so `known_at = now()` means active-only, and a past `known_at` replays exactly what was retrievable then);
  - merges full-text and vector ranks with RRF and also returns `sim` (cosine similarity); the vector branch runs only `where q_emb is not null`.
  - Two queries run: the original and an English rewrite (Gemini, low reasoning effort). Merge both lists by RRF and keep the top 8.
  - **Offline or embedding API down:** `q_emb = null` → full-text only; the answer shows the matching passages with citations.
- **Aliases:** `config/aliases.yaml` maps every spelling (Rameshwaram/ராமேஸ்வரம், border line/எல்லைக் கோடு/IMBL, vanjiram/Seer fish) to one slug via `ty_common.aliases.canonical()` (NFKC + whitespace + casefold, no LLM). Used for query normalisation, `kb_chunks.topics` at ingest, and spoken harbour names → harbour id + `near`. Test: every alias maps to exactly one slug.
- **Answer contract:** document-based sentences carry `[K1]…[K8]` **plus a verbatim quote**, returned as structured output `{"marker": "K3", "quote": "…"}`. The validator removes sentences with fake or missing markers **or a quote that is not a verbatim substring of that chunk** (`ty_common.quotes.is_verbatim`: NFKC + curly quotes + whitespace normalised, ≥ 12 chars). Quotes stay in the document's language and are never translated. Simple-mode phrase slots from documents (ban dates etc.) are filled from the verified quote; numbers must appear in the cited chunk or a tool result. If the best `sim` is below `RAG_MIN_SIM`, say nothing relevant was found and name the official source.
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

**Tracing rule:** `ty_common.telemetry.init_tracing(service)` sets exactly one tracer per process — TraceRoot when `TRACEROOT_ENABLED=true` (refuse to start if `ENV=live`), else Azure Monitor (Tier 1) or OTLP → otel-lgtm. `run()` wraps the event stream in `trace_context(thread_id, user_sub, lang, mode, versions)` (user id = salted SHA-256 prefix); the validator calls `record_guardrails({...})` with `ungrounded_number`, `quote_dropped`, `language_mismatch`, `rewritten`, `template_fallback`. Copy the module from specification Section 10.4.

**Memory (four layers — implement exactly these, nothing LLM-extracted):**

| Layer | Store | Lifetime |
|---|---|---|
| Thread memory (messages + `OrcaState`) | Postgres schema `agent`: LangGraph checkpoints + `agent.threads(thread_id pk, user_id → auth.users on delete cascade, created_at, last_seen)` | 30 days after last use (worker nightly purge via `adelete_thread`) |
| User memory | `boats`, `user_prefs`, `trips`, `share_grants` under RLS | until the user deletes it |
| Evidence memory | Constraint Ledger in Neo4j + `answers` row | 180 days |
| Working memory | `ty_common.cache` | Section 7a TTLs |

- `POST /agent`: `current_user` (optional; none = anonymous) → `claim_thread`: first caller owns the thread; a different signed-in user → **403**; then build `LangGraphAGUIAgent(name="orca", graph=..., config={"configurable": {"auth_user": user}})` per request and stream. Copy `server.py`, the `agent` schema migration and the role grants from specification Section 6.4.5.
- One run per thread: Redis lock `thread:<id>` (120 s); a second concurrent request → 409.
- Checkpoints hold messages and graph state only: `last_cell` is H3; never phone, name, email or lat/lon.
- `agent` schema: no grants to `anon`/`authenticated` (never exposed through the Data API); `ty_agent` has rights only there; `ty_worker` has select/delete there for the purge.

**Validator node:**

1. All numbers grounded. Use a regex for numbers with units (m, km, nm, °C, knots, km/h, %, h) and `HH:MM` times; single digits are allowed.
2. Every `[Kn]` is in the retrieved set, and its quote is verbatim in that chunk (dropped quotes are counted as `guardrail.quote_dropped`).
3. Reply language = `lang`.
4. **Simple mode only:** the reply is assembled from `config/phrases/<lang>.yaml` templates and contains none of `PFZ`, `IMBL`, `H1`–`H8`.

On failure, rewrite once; after that, render the template from the ledger.

**Language flow:** Simple mode = approved phrases in the user's language (no translation). Free-form = draft in English → `sarvam-translate:v1` with international numerals → re-run the number check; if any number or time changed, send the English sentence plus the approved-phrase verdict instead. Document quotes stay verbatim in the issuer's language, with a labelled *Machine translation* below. Voice out with Bulbul only for Group A; Group B gets text, icons and pictograms. Offline, Simple-mode replies are approved-phrase templates (pre-rendered audio for Group A languages, only the user's language downloaded); there is no offline free-form reply.

Prompts live in `apps/agent/src/prompts/*.md`. The planner prompt + tool schemas come first and stay byte-identical across calls (Gemini implicit caching).

---

## 10. Simple mode and daily-use mechanics (build these before Expert mode)

**Phrases file** (approved wording only; the LLM fills slots):

```yaml
# config/phrases/en.yaml  (every <code>.yaml has the same keys plus:
#   status: draft | approved, reviewers: [two native speakers], reviewed_on: YYYY-MM-DD;
#   drafts come from sarvam-translate:v1; only approved files are released)
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
   - `watch_once` sends each signed-in fisher a **web push 30 min before their usual departure** (median of the last 10 trips; default 04:00 IST). Android: an Expo push (`priority: high` for critical); web build: a web push. Tapping it opens the brief screen, which auto-plays the Tamil voice; the brief is saved in SQLite (Android) or the service-worker cache (web).
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
  language text,                        -- BCP-47 of a released language; null = nearest released language to the device locale
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

## 11. Expert mode (web build of `apps/app`)

- **Layout:** full map (`OceanMap.web.tsx`); custom CopilotKit chat panel built on `useAgent`; Mission Control strip (behind a "Show how it works" toggle); departure slider.
- **deck.gl layers:** SST/chl heatmaps, PFZ polygons, IMBL/MPA/EEZ from PMTiles, route, boats.
- **CopilotKit frontend tools** (`useFrontendTool` + zod): `flyTo`, `showLayer`, `drawRoute`, `setTime`, `openLedger(answerId)`, `openCitation(chunkId)`; Expert-only tools are registered only on Expert routes.
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

- **Governance (spec Section 9.5) — enforce in the repo:**
  - `.github/CODEOWNERS`: `config/constraints.yaml`, `config/boats.yaml`, `config/qc.yaml` → safety owner; `config/phrases/`, `config/aliases.yaml` → language owner; `apps/agent/src/prompts/` and model settings → AI owner; `config/sources.yaml`, `kb/sources/` → data owner. Branch protection on `main`: all checks green; with a team, 1 code-owner review and no self-approval; **solo** (Annexure I), every change still goes through a pull request reviewed against `docs/review-checklist.md`, and governed files carry the `safety-hold` label, which a workflow keeps failing until 24 hours after the last commit.
  - CI fails if any of those files changes without a bump of the config version or prompt version.
  - Every answer row stores `model`, `prompt_version`, `config_version`.
  - Admin **kill switches** (audit-logged with a reason): *free-form chat off* (buttons, map, alerts and briefs keep working) and *alerts paused for a region* (official critical warnings still pass).
  - Kadal Mitra **Me → Help** names the grievance officer and contact, in every released language.
  - Model change = rerun golden set + red-team suite, compare with the previous release, record in `docs/releases.md`.

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

All ports are bound to `127.0.0.1`. Supabase runs via `pnpm supabase start -x imgproxy,edge-runtime,logflare,vector,supavisor`. App processes run natively via `make dev`. No model server runs on the laptop.

**`docker/Dockerfile.python`** (shared; `--build-arg SERVICE_DIR=<service>`):

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

**`docker/Dockerfile.copilot`:** `node:24-alpine`, `npm ci --omit=dev`, copy `src/`, `USER node`, `CMD ["node", "src/server.ts"]`. The server wraps the CopilotKit listener: `/health` answers `ok`; every other request needs `x-azure-fdid` = `FRONTDOOR_ID` when that variable is set.
**`docker/Dockerfile.web`:** `nginx:1.27-alpine` serving `apps/app/dist` (from `expo export -p web`) on 8080 with `try_files $uri /index.html`; the nginx config is a template filled from `FRONTDOOR_ID` at start-up and returns 403 when `$http_x_azure_fdid` differs (`/healthz` exempt).

**Front Door check in Python (`packages/ty-common/src/ty_common/edge.py`):** a Starlette middleware `FrontDoorOnly(app, exempt={"/health", "/ok"})` — when `FRONTDOOR_ID` is set, any request whose `x-azure-fdid` header differs gets 403. Mount it on channels. Copy it from specification Section 15.2.1.

**Tier 1 — live-testing environment, Azure `centralindia`, resource group `ty-live`.** Copy `infra/azure/{main,app,job,edge,monitor}.bicep`, `.github/workflows/deploy-azure.yml` and `tests/load/dawn_rush.py` exactly from the specification, Section 15.2. Validate with `az bicep build -f infra/azure/main.bicep` (must be warning-free) and `az deployment group what-if` before every deploy. Subscription: **pay-as-you-go**.

| Resource | Type | Size | Replicas | Ingress |
|---|---|---|---|---|
| `ty-vnet` / subnet `aca` (/23, delegated to `Microsoft.App/environments`) | VNet | — | — | — |
| `ty-env` | Container Apps environment, workload profiles, **`zoneRedundant: true`**, in the VNet (set at creation; cannot be added later) | — | — | — |
| `ty-web` | Container App | 0.25 vCPU / 0.5 GiB | 2–4 | external, **Front Door only**, `/healthz` |
| `ty-copilot` | Container App | 0.5 / 1 GiB | 2–6 | external, **Front Door only**, CORS = web origin, `/health` |
| `ty-channels` | Container App | 0.5 / 1 GiB | 2–6 | external, **Front Door only**, CORS = web origin, `/health` |
| `ty-agent` | Container App | 0.5 / 1 GiB | 2–6 | **internal**, `uvicorn server:app --host 0.0.0.0 --port 8123 --workers 1`, `/ok`, secret `agent-database-url` |
| `ty-mcp` | Container App | 1 / 2 GiB | 2–4 | **internal** |
| `ty-redis` | Container App (`redis:7.4-alpine` imported into ACR) | 0.25 / 0.5 GiB | 1 | **internal TCP 6379**, password from Key Vault, no persistence |
| `ty-watch` | Container Apps job | 0.5 / 1 GiB | — | cron `*/15 * * * *`, `python -m ty_worker.watch_once` |
| `ty-ingest` | Container Apps job | 1 / 2 GiB | — | cron `30 20 * * *` (UTC = 02:00 IST), `python -m ty_worker.ingest_once` |
| `ty-fd` + WAF policy `tywaf` | **Front Door Standard**, endpoints for web, copilot, channels | — | — | public HTTPS; WAF custom rules: 300 requests/min per IP; `/admin` only from India (GeoMatch `IN`) |
| `ty-ai`, `ty-oncall` | **Application Insights** (workspace-based), action group (e-mail + SMS +91), standard availability test on channels `/health`, alerts (≥ 2 failed locations; > 20 failed requests in 5 min), budget USD 400/month (80 % actual, 100 % forecast) | — | — | — |
| `ty-load` | **Azure Load Testing** (Locust) | — | — | — |
| Supabase **Pro** (Mumbai), Neo4j **AuraDB Professional**, Gemini paid tier | External services | — | — | — |

Other Tier 1 rules:

- **Secrets:** Key Vault (RBAC) only, referenced by `keyVaultUrl` + the user-assigned identity; the identity has `AcrPull` and `Key Vault Secrets User`. No secrets in Bicep, GitHub or images.
- **Wiring:** apps call each other by app name (`http://ty-mcp/mcp`, `http://ty-agent`, `redis://:<pw>@ty-redis:6379/0`). The phone app and the browser use only the Front Door hostnames.
- **Edge:** Container Apps hostnames stay resolvable, so every public app checks `X-Azure-FDID` against `FRONTDOOR_ID` (health paths exempt). The deploy smoke test proves: direct origin → 403, through Front Door → 200.
- **Logs and telemetry:** Log Analytics in Central India, 180-day retention, 2 GB/day cap (CERT-In); Application Insights on the same workspace.
- **CI/CD:** GitHub OIDC (`azure/login@v2`, no stored password) → `az acr build` per image → Bicep deploy with `imageTag` = commit SHA, in GitHub environment **`live`** (required reviewer) → smoke test through Front Door.
- **Budget:** ≈ USD 300–350/month for Azure plus AuraDB Professional and Gemini usage (Gemini 3.8 Flash prices double on 1 Jan 2027). Never scale below 2 replicas while testers are active; pause (`minReplicas 0`) only between test periods, announced to testers.
- **Load gate (Gate L1):** before go-live and after any change to the request path: 200 virtual users for 15 min through Front Door, p95 < 2 s, errors < 1 %.
- **Recovery:** RPO 24 h (Supabase Pro daily backups), RTO 4 h; restore drill before go-live and monthly.
- **Readiness (Gate LT):** no real user is invited until the specification's Section 15.3 gate is signed — DPIA, written consent, VAPT by a CERT-In empanelled auditor, on-call rota + runbook, restore drill, Gate L1, phrase sign-off for every released language.
- **Knowledge base:** the nightly `ty-ingest` job indexes new bulletins; large PDF sets are indexed from the laptop with `make kb-index TARGET=live`.
- **Push:** separate VAPID pairs and Expo build profiles for the laptop and Tier 1.
- **Phone on the laptop:** `make phone` runs `adb.exe reverse` for ports 8081, 8200, 8002 and 54321, so the Android development build reaches Metro, `ty-copilot`, channels and local Supabase at its own `localhost`. No tunnel.

---

## 14a. Client app — Expo universal app (Android + web)

Every interface is this one app. Android delivers **background geofencing** (alerts with the screen off, the app closed and no network) and **offline trip maps**; the web build serves Expert, analyst, officer and admin screens and iPhone users. Full design: specification Chapter 17.

**Stack (exact):**

- **Framework:** Expo SDK 57 (RN 0.86) + TypeScript + `expo-router`, run as a **development build** (`expo-dev-client`); Expo Go cannot run background location or MapLibre.
- **Maps:** one `OceanMap` contract (`src/map/types.ts`). `OceanMap.native.tsx`: `@maplibre/maplibre-react-native` v11 with **local PMTiles** (`pmtiles://file://…`; MapLibre Android ≥ 11.7.0); do **not** use `OfflineManager` packs with PMTiles. `OceanMap.web.tsx`: `maplibre-gl` + `pmtiles` protocol + deck.gl `MapboxOverlay`. MapLibre React Native has no web support.
- **Web target:** `react-dom` + `react-native-web`; `web.output: "single"`; web-only routes as `*.web.tsx` with a non-platform fallback; `public/sw.js` registered only when `Platform.OS === "web"`.
- **Styling:** `StyleSheet.create` + `src/ui/tokens.ts`; accessibility props mandatory.
- **Location:** `expo-location` + `expo-task-manager`.
- **Device services:** `expo-notifications`, `expo-sqlite`, `expo-file-system`, `expo-audio`.
- **Geometry:** Turf (`@turf/point-to-line-distance`, `@turf/boolean-point-in-polygon`).
- **Auth:** `@supabase/supabase-js` with AsyncStorage + `react-native-url-polyfill`; Android: `@react-native-google-signin/google-signin` → `signInWithIdToken` (Android OAuth client per build profile SHA-1; `webClientId` = the Supabase web client); web: `signInWithOAuth({ provider: "google" })`.
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
5. Define both tasks with `TaskManager.defineTask` at module top level in `src/tasks/trip.native.ts` and import `src/tasks` from the root layout (`trip.ts` is an empty web stub).

**Config (`app.config.ts`):**

- `platforms: ["android", "web"]`; `web: { bundler: "metro", output: "single" }`.
- Plugins: `expo-router`, `@maplibre/maplibre-react-native`, `expo-notifications`, `expo-sqlite`.
- `expo-location` with `isAndroidBackgroundLocationEnabled: true`, `isAndroidForegroundServiceEnabled: true` and a permission string explaining border safety.
- `expo-build-properties` with `usesCleartextTraffic: true` **only when `APP_ENV=development`**.

**Permissions:** foreground → full-screen explanation in the user's language → background. Background location needs a Google Play declaration.

**Offline maps:**

- Build `gom_basemap.pmtiles` with `pmtiles extract <protomaps build> gom_basemap.pmtiles --bbox=78.0,8.0,80.5,10.5 --maxzoom=12`, plus the layer PMTiles, into the public Supabase Storage bucket `mobile-maps` with a SHA-256 manifest.
- The app downloads them once on Wi-Fi, verifies the hashes, and writes a local style JSON.
- The trip pack (verdict ribbon, PFZ GeoJSON, warning polygons, route, phrase text + TTS audio) is saved to SQLite at brief time and at harbour exit.

**CopilotKit RN:**

- **Entry imports, first:** `import "react-native-get-random-values"; import "@copilotkit/react-native/polyfills";`.
- **Provider:** `<CopilotKitProvider runtimeUrl={`${EXPO_PUBLIC_COPILOT_URL}/api/copilotkit`} headers={{ Authorization: `Bearer ${jwt}` }} properties={{ mode, lang }}>` — `ty-copilot`, the same runtime for both targets.
- **Web check (Milestone 1, day 1):** run the headless provider and `useSeaTools` in the web export. If it fails, only `src/copilot/Provider.web.tsx` and `useSeaTools.web.ts` switch to `@copilotkit/react-core` with the same `runtimeUrl`; screens stay shared.
- **Chat:** `useAgent({ agentId: "default" })` + `useCopilotKit().runAgent({ agent })` with a custom `FlatList` UI.
- **Frontend tools:** `useFrontendTool` with zod for `flyTo`, `openWhy` (both targets) and the Expert tools of Section 11 (web).
- **Voice:** `expo-audio` → `ty-channels /stt` (Sarvam); replies play from the `tts` cache URL.
- **Server pushes:** `getExpoPushTokenAsync` → `POST /push/subscribe` with `kind: "expo"` (`push_subscriptions.kind in ('web','expo')`). The **same worker** sends them: `httpx` POST to `https://exp.host/--/api/v2/push/send` with `EXPO_ACCESS_TOKEN`, after the alert budget and quiet-hour checks. Do not use Supabase database webhooks + Edge Functions for push.
- **Metro:** `metro.config.js` from `expo/metro-config` plus the documented `resolveRequest` override that resolves only `jose` with the `browser` condition.

**Screens:** Simple tabs Today · Map · Trip (Android) · Alerts · Me on both targets; `family/[boatId]`; Expert, analyst, officer and admin routes on the web build only (role + `aal2` checked in the route layout, RLS again in the database).

**Simulation:** Android Emulator (Android Studio on Windows, API 34 Google APIs x86_64).

- `scripts/sim_boat.py --gpx` exports the boat track.
- Load it under **Extended controls → Location → Routes** for demos.
- For repeatable tests, `scripts/replay_gpx.py` sends `adb emu geo fix <lon> <lat>` per point (run with Windows Python).
- The emulator reaches WSL services at `10.0.2.2` (Metro :8081, `ty-copilot` :8200, channels :8002); a USB phone uses `make phone` (`adb reverse`).
- Daily development on a real phone over USB; the emulator only for GPX and airplane-mode tests (laptop memory).

**Builds and release (copy `eas.json` and `.github/workflows/android-release.yml` from specification Section 17.12):**

- `eas.json`: `cli.appVersionSource: "remote"`; profiles `development` (dev client, laptop), `preview` (release-signed APK → Tier 1, team QA), `live` (release-signed **APK**, `autoIncrement`, internal distribution → testers), `store` (**AAB**, `autoIncrement` → `eas submit` to Play track `alpha` = closed testing). Public values come from **EAS environment variables** (`eas env:create --environment production …`), never from committed files.
- Signing: **EAS-managed release keystore** (`eas credentials`), backed up by the release owner; its SHA-256 fingerprint is the repo variable `RELEASE_CERT_SHA256`. Add the release SHA-1 **and** the Play App Signing SHA-1 to the Google OAuth Android client.
- `app.config.ts`: `version`, `android.allowBackup: false`, `updates: { enabled: false }` (no over-the-air updates in live testing); cleartext HTTP only in `development`.
- Release = tag `kadal-mitra-v<version>` → `android-release.yml` (environment `live`, reviewer approval): tsc + Jest + i18n check → `eas build --profile live` → verify with `apksigner` (certificate = `RELEASE_CERT_SHA256`) and `aapt2` (package, `targetSdkVersion:'36'`, no cleartext) → `sha256sum` → `gh release create` with APK + checksum → `eas build --profile store --auto-submit`.
- Channels `GET /app/version` → `{latestVersionCode, minVersionCode, apkUrl, sha256}`; app shows an update banner, and a full-screen update prompt below `minVersionCode` (alerts keep working). `POST /client-errors` → Application Insights (no personal data).
- Play Console: Data safety, privacy policy (`/privacy` on the web build), 18+ audience, background-location declaration + video; closed test with the consenting testers (≥ 12 for 14 days on a personal developer account).
- Web: `npx expo export -p web` → `dist/` → `docker/Dockerfile.web`. Expo push on Android needs FCM V1 credentials uploaded with `eas credentials`.

**Walkthrough capture (specification Section 17.14 — copy the files from there):**

- **Everything, every released language.** `apps/app/e2e/coverage.yaml` is the 46-feature catalogue of specification Table 17-12 (feature → flow → screenshot names → video chapter). Android flows `apps/app/e2e/maestro/flows/A01-onboarding … A21-rtl.yaml` (plus `00-launch.yaml`, `R01-release-smoke.yaml`, `scenarios.yaml`), web flows W01–W08 in `apps/app/e2e/web/walkthrough.spec.ts` (`page.screenshot`, `recordVideo`, `?lang=`, staff TOTP via `otpauth`). Every step `takeScreenshot: <flow>/<NN-step>`; selectors are `testID`s; language via `-e APP_LANG=<code>`; questions from suggested-question chips, never typed; trip with Maestro `travel` and `setAirplaneMode`.
- `scripts/capture_all.sh <capture-apk> <live-apk> [langs]` (default: every released language) → per language `scripts/capture_walkthrough.sh` (emulator, demo-mode status bar, install the **`capture`** build, scrcpy full-length recording, each flow after `scripts/scenario.sh <flow>`, `segments.json`) and the Playwright web flows → `scripts/release_smoke.sh` (live APK on Tier 1) → `scripts/check_coverage.py` (fails on any feature without screenshots in any language or without a video scene) → `artifacts/app-walkthrough/<version>-<date>/{README.md, coverage-report.json, apk/, release-smoke/, <lang>/{android,web,video,maestro}}`.
- Scenario hooks: channels `POST /admin/capture/scenario` (`brief-now`, `simulated-warning`, `no-safe-window`, `stale-data`, `llm-offline`, `kill-switch-chat`, `fault-next-request`, `update-required`, `normal`) exists only with `ENV=local` and `CAPTURE_SCENARIOS=1`, requires `X-Capture-Token`, returns 404 in Tier 1 (tested). The `capture` EAS profile (laptop backend, every language enabled) is never distributed.
- `.claude/settings.json` allows the capture scripts, `scenario.sh`, `check_coverage.py`, `adb.exe`, Playwright, ffmpeg/ffprobe, sha256sum, jq and `gh release upload`; `.claude/commands/walkthrough.md` is the `/walkthrough <capture-apk> <live-apk> [langs]` command (run, fix failing flows up to three times, fix every coverage gap by adding steps, read every screenshot in every language and caption it, check manifests and checksums, zip and upload).
- `artifacts/` is git-ignored. Only the team's test Google account and the emulator's mock location appear in captures.
- The capture script runs `00-launch.yaml` (clear state) and then each flow separately, writing `video/segments.json` (start/end ms of each flow in the recording) for the story video.

**Story video (specification Section 17.15 — copy the code and chapter table from there):**

- **Remotion** project in `video/` (pnpm workspace `@repo/video`): `npx create-video@latest --blank`, then `npx remotion add @remotion/transitions @remotion/media @remotion/captions`. Built solo, the Remotion Free License covers it (individuals and teams of up to three); a team of four or more needs a Company License seat per person writing Remotion code.
- Compositions `KadalMitraStory` (1920×1080) and `KadalMitraStoryVertical` (1080×1920), 30 fps, length from `calculateMetadata` reading `public/timeline.<lang>.json` (sum of scene frames minus 12-frame fades).
- Sixteen chapters (Table 17-14) built from scene types in `video/src/scenes/` (Illustration, PhoneShots, PhoneClip, BrowserShots, BrowserClip, Diagram, Title); every scene lists the features it shows in `covers`; no length limit; shared `PhoneFrame`, `BrowserFrame` (plain CSS, no device or browser brand), `TapRipple`, `Callout`, `CaptionBar` (right-to-left aware), `ChapterCard`, `LedgerDiagram`; motion with `interpolate`/`spring`; scenes joined by `TransitionSeries` + `fade()`; narration with `<Audio>` and clips with `<Video>` from `@remotion/media`; app fonts and `tokens.ts` colours.
- `video/scripts/build_assets.py <walkthrough-root> <lang>`: copies screenshots, cuts clips from `full-walkthrough.mp4` with ffmpeg using `segments.json`, uses `video/recordings/<lang>/<scene>.wav` when present (Group B) or synthesises narration from `video/script/narration.<lang>.yaml` with Sarvam `bulbul:v3` (Group A, `sarvam_code` from `languages.yaml`), measures durations with ffprobe, writes `timeline.<lang>.json`. `video/public/` is generated and git-ignored.
- Honesty: every app frame is a real capture of the released build; no invented screens, user counts, savings or accuracy figures (only dated numbers from `docs/eval-report.md`); the simulated warning keeps its SIMULATION label; the fisher is a fictional drawn character; music only CC0 or licensed and listed in `THIRD_PARTY.md`.
- `video/scripts/render_all.sh <walkthrough-root> [langs]` renders, for every released language, the full video, the portrait cut, one MP4 per chapter (`--frames`) and `chapters.txt`; preview with `npx remotion studio`.

## 15. Milestones (one PR each; stop and summarise after each)

| # | Milestone | Acceptance criteria |
|---|---|---|
| 1 | Scaffold | Starter cloned, its Next.js app removed, Expo app created in `apps/app` (Android + web) and **CopilotKit web check passed or fallback chosen**; `services/copilot` runtime answering; uv packages (`tarangyukti`, `ty-channels`, `ty-worker`, `ty-common`) with editable `ty-common`; `ty_common.cache` (`@cached`, `fingerprint`, `invalidate`) with its tests; settings modules; `.env.example`; `infra/docker-compose.yml` healthy; Supabase local with `vector` + `postgis`; Makefile `dev`; CI (ruff, mypy, pytest, eslint, tsc, build) green |
| 2 | Data tools + cache + snapshots | `ToolResult` for marine_forecast, imd_warnings (snapshot fixture), incois_alerts, pfz_incois, sst_grid, chl_grid, fence_check, geo_distance; all tools wrapped with `@cached(ns="tool")`; `snapshots` bucket migration; `make snapshot`; `DATA_MODE=snapshot` works offline; unit + tool + cache tests |
| 3 | Yukti engine + route | H1–H8, S1–S5 from YAML; outcome mapping; earliest-window search; time-expanded A*; Neo4j ledger write; Hypothesis property tests (a new warning never makes a trip safer; tightening a limit never adds windows; every refusal has a failed hard constraint) |
| 4 | RAG | `kb_*` migrations + `kb_hybrid_search`; Docling ingest with sanitiser + versioning + cross-document supersession; `config/aliases.yaml` + `kb_chunks.topics`; `known_at` replay in `kb_hybrid_search`; Gemini Embedding 2 (768-d) + full-text-only path when `q_emb` is null; `RAG_MIN_SIM` calibrated; `kb_search` tool; golden set + `make eval-rag` gates met |
| 5 | Agent graph | Planner + 8 specialists; validator (numbers, citations, **verbatim quotes**, language); locked ledger schema with `valid_at`/`known_at`; `tests/failures/failures.yaml` harness wired into `make test`; fallback Gemini → ledger templates (tested with the key revoked); reasoning effort per agent; `server.py` with `AsyncPostgresSaver`, owner-bound threads, 30-day purge; OTel traces visible in Grafana |
| 6 | Simple mode on both targets | Simple tabs; `/push/subscribe` + `push_subscriptions` (`expo` + `web`); worker push (Expo + pywebpush) + `make push-test`; web `public/sw.js` + manifest; `make phone`; Phrases files; Sarvam STT/TTS (`expo-audio` → `/stt`, `/tts` mp3); instant acknowledgement; four buttons; "Why?"; voice onboarding (**language picker first**: released languages in their own script, spoken where Bulbul has a voice) + consent + Add-this-phone QR; i18next catalogues for every language (no built-in language) and the CI key check; **morning brief** + `make brief-now`; sunlight theme from `tokens.ts`; Simple replies contain no codes (test) |
| 7 | Expert console (web build) | `OceanMap.web.tsx` + layers + CopilotKit frontend tools; map contract test on both targets; Sea Signal + ribbon; ledger; citations; departure slider; Mission Control toggle; analyst tools; Playwright hero flow |
| 8 | Alerts, trips, family, feedback | `watchPosition` while open (every 60 s) + `sim_boat.py` → `positions`; geofence 5 km / 2 km; trips open/close by geofence and button; family notice; feedback; alert budget + quiet hours; frozen-clock tests |
| 9 | Auth, RLS, admin | Google sign-in; roles hook; MFA for staff; RLS on every table with cross-user tests; My data download/delete; audit chain + verify; `/admin` pages incl. daily-use measures, **Replay** and Guardrail review → failures dataset; `GET /sources/{kind}/{id}`; kill switches; Help screen with grievance officer; `CODEOWNERS` + branch protection + version-bump CI check |
| 10 | Tier 1 live-testing environment + docs | `docker/` files; `FrontDoorOnly` middleware + nginx FDID check; `infra/azure/*.bicep` warning-free; `deploy-azure.yml` with OIDC, environment `live` and Front Door smoke test; zone-redundant Container Apps (Central India) behind Front Door + WAF; Application Insights alerts reach the on-call phone; Supabase Pro + AuraDB Professional live; Gate L1 load test passed; restore drill logged; budget alert; Tier 1 VAPID pair + Expo push to the `live` APK + web push to desktop Chrome; `android-release.yml` produces a verified, checksummed APK and a Play closed-testing release (Gate M-G6); `scripts/demo.sh` + `smoke.sh` green from cold boot; README, THIRD_PARTY.md, eval and test reports |
| 10a | Every Indian language | `languages.yaml` (code, sarvam_code, group, script, rtl, status, pilot_coasts); phrase files and i18n catalogues for all 23 languages drafted with `sarvam-translate:v1`; Noto fonts for every script; right-to-left screens; per-language golden set (20 questions) + 20 cross-language + promptfoo language tests; harbour-state language suggestion; no hard-coded default language anywhere (test); a language moves to released only with two signed reviews |
| 10b | Walkthrough capture | `testID` on every interactive element; flows A01–A21, W01–W08, R01 and scenario hooks; `capture_all.sh` passes for every released language with one screenshot per step, a full-length MP4 per language and the release smoke; `check_coverage.py` reports no gap; `/walkthrough` works; zip attached to the release (Gate M-G7) |
| 11 | Android background and offline (before the finale) | Gates M-G1…M-G4 and W-G1…W-G2 from specification Section 17.13: dev build + Google sign-in + live verdict; screen-locked GPX replay raises 5 km / 2 km alerts and harbour exit/enter toggles trip mode; airplane mode keeps map, route, border line, brief and alerts working and the outbox syncs later; Tamil chat drives `flyTo`/`openWhy` with audio on Android and web; web Expert flow and web push pass. M-G5 (two fishers for a week) is the pilot |
| 12 | Story video | `video/` Remotion project; scene types; English reference script covering all 46 features in 16 chapters; narration files for every released language (Bulbul for Group A, reviewer recordings for Group B); `render_all.sh` renders, per released language, the full video (no length limit; expected 25–40 min), the portrait cut, one MP4 per chapter and `chapters.txt`; every feature present (coverage check); narration approved by each language owner (Gate V-G1) |
| 13 | Agent improvement loop | `ty_common.telemetry` (one tracer per process, SEC-14 guard); TraceRoot in agent, mcp and `ty-copilot`; `make trace-evals` traces every released language's golden set, cross-language set, promptfoo suite and `failures.yaml`; six detectors from `docs/improvement/detectors.md` created in TraceRoot; `scripts/eval_traceroot.py` (TraceRoot `evaluate()`, `candidate_version` = git SHA); `docs/improvement/report.md` with measured detector rates per language and closed signals (each with a failures-dataset row) |

---

## 16. Testing requirements

| Layer | What to test |
|---|---|
| Unit | Distances, geofence rings, risk levels, ban calendar, QC ranges, H3 keying, phrase slot filling |
| Property | The Yukti invariants in Milestone 3; route never enters removed cells or bad-weather time steps |
| Tool contract | Every tool online (respx-mocked), cached, stale, snapshot |
| Cache | L1/L2 hit; new source version → new key; config change → new keys; 200 concurrent calls → 1 computation; stale-if-error; tag invalidation clears L1 in other processes; `CACHE_DISABLED=1` gives same answers; E2E scan finds no phone, email or lat/lon in any cached value (fakeredis) |
| RAG | Expired advisory never returned; superseded advisory hidden after `superseded_at` but returned for an earlier `known_at`; region filter; `simple` FTS matches every Indian script; RRF merge; eval gates per released language |
| Languages | All i18n keys present per released language; every phrase slot fillable; translation keeps numbers and times identical (else English fallback); RTL screens for Urdu, Kashmiri, Sindhi; no clipped text at 200 % font scale; unreleased languages absent from the production picker |
| Provenance | Paraphrased/stitched quotes rejected, exact spans (whitespace/NFKC variants) accepted; every alias → one slug; `/sources/answer/{id}` refuses other users; replay reproduces a past ledger from its snapshot |
| Failures dataset | Every row of `tests/failures/failures.yaml` passes; removing a row fails CI |
| Grounding | Invented "2.7 m" rejected; times like 05:30 handled; fake `[K9]` removed; language mismatch caught |
| Daily-use | Brief once, 30 min before learned departure; quiet hours; ≤ 3 non-critical alerts a day; trip open/close; one family notice |
| Security | RLS isolation; officer `aal2` + warning-area rule; missing token → 401; another user's push subscription unreadable; 410 from the push service deletes the subscription; out-of-EEZ input rejected; audit tamper detected |
| LLM safety | promptfoo: injection inside a bulletin changes nothing; out-of-coverage refusal; language in → same language out for every released language; no ungrounded numbers |
| Mobile (M11) | Jest: Turf distance within 50 m of PostGIS on fixtures; on-device alert budget; emulator GPX replay with screen locked and in airplane mode |
| E2E | Playwright against the exported web build: public Simple verdict → Why? → Expert → ledger → login → save boat → share with family → admin audit shows events; Android: emulator GPX replay, screen locked and airplane mode |
| Thread memory | Two `server.py` processes: turn 2 on the other process keeps turn 1; restart keeps it; another user's token on the thread → 403; account deletion removes its threads; purge removes threads idle 30 days; no phone, name or lat/lon in any checkpoint |
| Governance | `CODEOWNERS` covers every governed file; governed change without a version bump fails CI; kill switch turns free-form chat off while buttons still answer |
| TraceRoot | `init_tracing` raises with `ENV=live` + `TRACEROOT_ENABLED=true`; no `TRACEROOT_*` in `infra/azure/*.bicep` (CI grep); traces show only hashed test ids; tool spans and guardrail metadata present on a traced golden-set run |
| Infra | `az bicep build` warning-free; `what-if` shows no unexpected deletes |
| Edge | Direct `*.azurecontainerapps.io` request → 403; through Front Door → 200; 301st request in a minute from one IP → 429 |
| Load | Gate L1 on Azure Load Testing: 200 users, 15 min, p95 < 2 s, errors < 1 % |

CI runs everything except tests that call live models (`-m "not llm"`). Run those on the laptop with `make test-local` and commit the report.

---

## 17. Coding conventions

- **Python:** ruff + `mypy --strict` on services; async I/O; `httpx.AsyncClient` with timeouts; no bare `except`; structured JSON logs with request id.
- **TypeScript:** strict; Zod for all external data; shared code first, platform files (`*.native.tsx` / `*.web.tsx`) only where an API differs (map, background tasks, charts, service worker); every interactive element has `accessibilityRole`, `accessibilityLabel` and a stable kebab-case `testID` (language-independent, e.g. `lang-ta`, `turn-on-alerts`, `tab-trip`) used by the Maestro walkthrough flows.
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
- Run `langgraph dev` or an in-memory checkpointer outside a developer's own debugging; use the LangGraph Agent Server.
- Merge a change to safety config, phrases, prompts or the model without a code-owner review and a version bump.
- Send a real user's conversation, id or position to TraceRoot, or set any `TRACEROOT_*` variable in Tier 1; merge a TraceRoot-suggested fix without the gates and a failures-dataset row.
- Use LangSmith, Chainlit, Streamlit, Railway or `langgraph-supervisor`; add Ollama, any local or self-hosted model, a reranker model or a fine-tuned model.
- Add Next.js, Vercel, Render or a second client codebase; build a native iOS app; use NativeWind or Tailwind in the app.
- Expose `ty-agent`, `ty-mcp` or `ty-redis` with external ingress; serve a public app without the `X-Azure-FDID` check; drop any Tier 1 app below 2 replicas while testers are active; put a secret in Bicep, GitHub variables, an image or an `EXPO_PUBLIC_*` value.
- Use Expo Go for the Android app, use MapLibre `OfflineManager` packs with PMTiles, or ship cleartext HTTP in non-development builds.
- Ship an Android build to testers that was not built by `android-release.yml` from a tag, signed by a key other than `RELEASE_CERT_SHA256`, or delivered by an over-the-air update; commit a keystore, `play-service-account.json` or an `EXPO_TOKEN`.
- Put a mocked-up or AI-generated app screen, an invented statistic or a real tester's face, name or position in the story video.
- Add Terraform, Jenkins, Datadog, Firecrawl, Kafka, Selenium, Prisma, Elasticsearch, Neon, Postman collections or a payment gateway.
- Expose `SUPABASE_SERVICE_ROLE_KEY`, `REDIS_URL` or any secret to the browser or bake it into an image.
- Add Memgraph, Graphiti, Inngest, LLM claim/entity extraction into a graph, AKS / self-managed Kubernetes or Langfuse in the prototype; let an LLM write Cypher or invent ledger labels; replace or paraphrase a `quote` (a labelled machine translation may be shown below it).
- Add Telegram, WhatsApp or any chat bot in the prototype; put the VAPID private key in the web app; ask for notification permission before the user taps **Turn on alerts**; put coordinates in a push payload.
- Hard-code thresholds, phrases, keys, interface strings or real user coordinates; release a language whose phrase file is not `approved`; let machine translation write a safety sentence.
- Contradict an active official warning, or say "safe" without "advisory only".
- Add features outside the current milestone without asking.

---

## 19. When unsure

Pick the simplest option that keeps Section 2. Leave a `TODO(tarangyukti):` explaining the assumption, and list every assumption in the PR description. If a library's current API differs from this file, follow its current documentation and note the difference in the PR. For anything not covered here, follow `docs/TarangYukti_Engineering_Specification_v2.2.md`.
