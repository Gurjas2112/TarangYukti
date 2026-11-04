# TarangYukti

A conversational, constraint-reasoning marine copilot that turns ISRO/INCOIS ocean data into explainable,
voice-first safety verdicts for small-boat fishers (prototype region: Gulf of Mannar + Palk Bay).

- Build contract: [AGENTS.md](AGENTS.md) (same text as `.github/copilot-instructions.md`)
- Full design: [docs/TarangYukti_Engineering_Specification_v2.2.md](docs/TarangYukti_Engineering_Specification_v2.2.md) — wins on any disagreement
- Built one milestone at a time (AGENTS.md §15).

## Status

| Milestone | State |
|---|---|
| 1 · Scaffold | **Done** — see below |
| 2 · Data tools + cache + snapshots | **Done** — see below |
| 3 · Yukti engine + route | **Done** — see below |
| 4 · RAG | **Done** — see below |
| 5 · Agent graph | **Done** — see below |
| 6 · Simple mode on both targets | Next |

## Milestone 5 — the agent

`apps/agent` serves the LangGraph agent over AG-UI (`make agent`, `POST /agent`, `GET /ok`); `ty-copilot` forwards to it.

- **Graph**: prepare (Language agent: keeps the reply language, mode, boat) → button flow (deterministic, no LLM)
  or planner (Gemini, `create_agent`, 7 specialists wrapped as tools: data discovery, weather, ocean, geospatial,
  knowledge, Yukti, explain) → validator → finalize.
- **Specialists** call the MCP tools in parallel and return compact digests with IST times; the planner only sees
  digests, so every figure it can use comes from a ToolResult.
- **Validator**: numbers and times grounded in the turn's tool outputs, `[Kn]` citations verbatim, no codes in
  Simple mode, never "safe" without "advisory"; one rewrite, then a template from the ledger.
- **Simple mode** shows the verdict from approved phrases only; free text is drafted in English and translated
  with Sarvam (international numerals; English is sent if any number changed). Footer always added.
- **LLM down** (timeout or API error): button flows still answer from the Yukti ledger; free-form questions get the
  "needs the internet" phrase. Planner effort is `low` by default (`ORCA_PLANNER_EFFORT`): medium and high hit the
  20 s timeout in live runs.
- **Memory**: thread state in Postgres schema `agent` (`AsyncPostgresSaver`); the first caller owns a thread
  (another user → 403); one run per thread (Redis lock → 409); nightly purge after 30 days (`make agent-purge`).
  Verified: a new server process continues a conversation started before the restart.
- **Failures harness**: `tests/failures/failures.yaml` (+ `ids.lock`) is replayed by `make test`; rows can't be removed.
- **Telemetry**: one tracer per process (OTLP → Grafana, Azure Monitor in Tier 1, TraceRoot for test runs only);
  exported spans are scrubbed of tokens, phones, e-mails and coordinates. Seeing traces in Grafana needs Docker
  (`make infra-up`) — not verified yet because Docker Desktop was not running.

## Milestone 4 — knowledge search (RAG)

`kb_search` (MCP tool) answers "what does the law / order / bulletin say?" with up to 8 cited passages
`[K1]…[K8]` from official documents, in any language.

- **Corpus** (`kb/sources/manifest.yaml`): Maritime Zones of India Act 1976, Tamil Nadu Marine Fishing
  Regulation Act 1983 + 2017 amendment, CMFRI Marine Fish Landings 2024, three team-written safety SOPs
  (DRAFT), and the region's live IMD / INCOIS / SDMA CAP alerts with their validity windows.
- **Ingest** (`make kb-index`, worker): fetch (allow-listed) → SHA-256 skip if unchanged → Docling →
  sanitiser (quarantines prompt-injection text) → HybridChunker (≤ 512 tokens) → topics from
  `config/aliases.yaml` → Gemini Embedding 2 (768-d) → Postgres. A new version supersedes the old one; a CAP
  alert supersedes the alerts it references. Nothing is deleted.
- **Search**: original question (aliases expanded) + an English rewrite (Gemini) → `kb_hybrid_search`
  (pgvector + full text, filtered by validity, supersession, region, and `known_at` for replays) → RRF → top 8.
  Without the embedding service it falls back to full text. Below `RAG_MIN_SIM` it reports "nothing relevant".
- **Evaluation** (`make eval-rag`, report in `docs/eval-report.md`): 60 golden questions (30 English, 30 Tamil)
  in `apps/agent/tests/golden.jsonl`; recall@8 0.958 in both languages (gate 0.9). `RAG_MIN_SIM` calibrated to
  0.70. Ragas answer-quality scores need the agent and come with Milestone 5.
- **Database**: `make db-migrate` applies `supabase/migrations`; `make db-roles` creates `ty_api` (reads as
  `authenticated` under RLS), `ty_worker` and `ty_agent` and writes their URLs into `.env`.

Not indexed yet: the PIB fishing-ban release (PIB refuses automated clients — save the page from a browser to
`kb/sources/captured/pib-2114930.html` and run `make kb-index`), and the Tamil Nadu Rules 2020 (the
department's link returns 404). Document search uses the cloud database, so it needs the network.

## Milestone 3 — Yukti constraint engine

`yukti_evaluate` (MCP tool) answers "can I go?" for a boat type, a start point and an optional fishing
spot: it checks H1–H8 (hard) and S1–S5 (soft) from `config/constraints.yaml` and `config/boats.yaml`,
maps the result to **GO / CAUTION / NO-GO**, searches departures every 30 min for 24 h for the
**earliest window** and the **recommended** one, and writes the Constraint Ledger to Neo4j
(`answer_id`). `route_safest` returns the time-expanded A* route on H3 cells.

- **H1** counts IMD, INCOIS **and state disaster authority (SDMA)** alerts — a deliberate extension of the
  spec decided on 2026-11-03; thunderstorm/lightning alerts are H7.
- Routes never enter land (Natural Earth 1:10m), the marine park, or cells within 5 km of the IMBL, and
  skip cells whose forecast at the hour the boat is there breaks the boat's limits.
- "Unknown" is never GO: missing or stale inputs fail H8; a missing forecast fails H5/H6 as unknown.
- With `DATA_MODE=snapshot` the engine evaluates as of the snapshot's capture time.
- S5 (two wave sources agree) is "not tested" until a second wave source exists; S1 needs a PFZ advisory.
- The ledger stores no names, phones, coordinates or user cells; replay uses `known_at <= answer time`.

## Milestone 2 — data tools

Tools on the MCP server (`services/mcp`, `:8001/mcp`), each returning a `ToolResult` and cached with
`@cached(ns="tool")` (raw coordinates never enter the cache; keys use H3 cells):

| Tool | Live source | Notes |
|---|---|---|
| `marine_forecast` | Open-Meteo Marine + Forecast | waves, swell, currents, SST, wind; QC ranges from `config/qc.yaml` |
| `sst_grid` / `chl_grid` | NOAA CoastWatch ERDDAP (OISST NRT, NOAA-20 VIIRS) | cloud gaps left missing; age vs freshness limit in notes |
| `imd_warnings`, `incois_alerts` | NDMA SACHET (official CAP alerts) | free; real issuer read from each alert (state authorities relay INCOIS alerts) |
| `pfz_incois` | snapshot only | INCOIS publishes PFZ advisories as web pages only |
| `fence_check`, `geo_distance` | local layers | IMBL from the 1974/1976 treaty positions; marine park from WDPA |

```bash
make snapshot DATE=2026-11-02      # capture live sources → data/snapshot/<date>/ + manifest → Supabase Storage
make sim-warning DATE=2026-11-02   # add the labelled SIMULATED INCOIS high-wave warning (CLEAR=1 removes it)
DATA_MODE=snapshot SNAPSHOT_DATE=2026-11-02 …   # every tool reads only the snapshot (works offline)
```

With `DATA_MODE=online`, a tool whose live source is down falls back to the snapshot with
`cache="snapshot"`, `confidence="low"` and a note; if there is no snapshot it returns
`data.available=false`. The cache is bypassed (not fatal) when Redis is not running.

## Repository

```
apps/app            Expo SDK 57 + Expo Router — Kadal Mitra (Android) + web build, one codebase
apps/agent          LangGraph agent on Gemini; FastAPI server (/ok now, AG-UI /agent in Milestone 5)
services/copilot    ty-copilot — CopilotKit runtime (Node 24) → ty-agent
services/mcp        package "tarangyukti" — FastMCP data tools, Yukti engine, RAG
services/channels   ty-channels — voice/device API (/health now)
services/worker     ty-worker — scheduled jobs, push sender
packages/ty-common  shared settings, ToolResult, two-tier cache (@cached)
config/             constraints, boats, qc, sources, languages (23), aliases, phrases
supabase/           config.toml, migrations (postgis, vector, snapshots bucket)
infra/              docker-compose (redis, otel-lgtm; neo4j optional)
```

## Quick start (Windows Git Bash or WSL)

Needs: uv, Node ≥ 24, pnpm 10, Docker (for Redis + Grafana).

```bash
cp .env.example .env                    # fill real values (never commit)
cp apps/app/.env.example apps/app/.env.local
cp services/copilot/.env.example services/copilot/.env
make install                            # pnpm install + uv sync for every Python project
make infra-up                           # redis + otel-lgtm
make test lint typecheck
make dev                                # agent :8123, mcp :8001, channels :8002, copilot :8200, Metro :8081
```

## Milestone 1 decisions and assumptions

- **Dev databases are cloud:** Supabase (Mumbai) and Neo4j AuraDB, instead of the local Supabase stack in spec §12.3.7.
  Apply migrations with `pnpm dlx supabase link --project-ref <ref>` then `pnpm dlx supabase db push`, and create
  service roles with `scripts/db_roles.sh`. The local Neo4j container is opt-in (`--profile local-neo4j`).
- **CopilotKit web check passed:** the web export renders with `@copilotkit/react-native/headless` and reaches
  `ty-copilot` (`/api/copilotkit/info` → 200) with no console errors, so no `react-core` fallback is needed.
- Routes live in `apps/app/app/` (spec layout), not the SDK 57 template's `src/app/`.
- i18n is a minimal catalogue lookup until Milestone 6 brings i18next; every language in `config/languages.yaml`
  is `draft` until two native-speaker reviewers sign its phrase file.
- Docling, Ragas and Schemathesis are added in their milestones (4 and later), not now.
- CopilotKit runtime telemetry is opted out (`COPILOTKIT_TELEMETRY_DISABLED=true`).
- **Azure is for a hosted demo prototype only**, not live testing with real users. After Milestones 2–7, the
  demo deploys on pay-as-you-go as a *slim demo tier*: the spec's Container Apps + Bicep + GitHub deploy
  pipeline, but 1 replica that scales to zero, no zone redundancy and no Azure Load Testing; Front Door + WAF
  optional. The full Tier 1 of spec §15.2 (≥ 2 replicas, zone-redundant, load gate) applies only if live testing
  with real users is ever started.

Licence: see [LICENSE](LICENSE).
