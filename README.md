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
| 2 · Data tools + cache + snapshots | Next |

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

Licence: see [LICENSE](LICENSE).
