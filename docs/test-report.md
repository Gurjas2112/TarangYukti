# Test report

State of the automated checks at Milestone 10 (2026-11-04), run on the development laptop (Windows 11, Python 3.12,
Node 24). CI runs the same suites except tests that call live models (`-m "not llm"`) or the dev database.

| Suite | Command | Result |
|---|---|---|
| Shared library (cache, phrases, trips, auth, edge, governance) | `cd packages/ty-common && uv run pytest` | 69 passed |
| MCP tools, Yukti engine, RAG, brief, ocean tools, failures rows | `cd services/mcp && uv run pytest -m "not llm and not gpu"` | 123 passed |
| Agent graph, validator, records, kill switch, failures rows | `cd apps/agent && uv run pytest -m "not llm"` | 39 passed |
| Channels API (public, signed-in, expert, trips, release) | `cd services/channels && uv run pytest` | 30 passed (+12 RLS skipped without the DB) |
| Cross-user row-level security on the dev database | `make test-rls` | 12 passed |
| Worker (push, budget, family notice, scheduler, ingest) | `cd services/worker && uv run pytest` | 20 passed |
| App (Jest: components, languages, map contract, UI actions) | `pnpm -C apps/app test` | 17 passed |
| Language catalogues (23 × 266 keys, variables) | `pnpm -C apps/app run check:i18n` | ok |
| Web end-to-end (Playwright on the exported build) | `pnpm -C apps/app e2e:web` | 3 passed (Expert hero flow, trip, family) + `@llm` chat flow passed |
| Smoke (laptop) | `make smoke` | all green |
| Azure templates | `make bicep` | 5 files build warning-free |
| Governance gate | `python scripts/check_governed.py HEAD~1 HEAD` | ok |
| RAG evaluation | `make eval-rag` | recall@8 0.958 (gate 0.9); see `docs/eval-report.md` |

Lint and types: Ruff and mypy `--strict` clean for every Python package; ESLint and `tsc --noEmit` clean for the app.

## Not yet verified

- Container images: Docker was not running on the laptop; images are built by ACR on the first deployment
  (`make run-prod` builds them locally when Docker is available).
- Azure deployment, Front Door 403/200 smoke, Gate L1 load test: need the pay-as-you-go subscription.
- Android: development build on a phone, background trip mode and offline maps (Milestone 11).
- OpenTelemetry traces in Grafana (needs Docker for `otel-lgtm`).
- Ragas answer-quality scores and the promptfoo red-team suite (Milestone 13).
