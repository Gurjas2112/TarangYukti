# TarangYukti Makefile (spec Annexure B). Runs in bash: WSL, Git Bash or CI.
-include .env
export

PY_PROJECTS := packages/ty-common apps/agent services/mcp services/channels services/worker
COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml

DATE ?= $(shell date +%F)
MCP := cd services/mcp && uv run python -m
WORKER := cd services/worker && uv run python -m

.PHONY: install infra-up infra-down dev test lint typecheck phone \
        channels outbox i18n-draft sim-boat housekeeping failures-pull snapshot snapshot-upload snapshot-download sim-warning layers \
        agent agent-purge smoke bicep brief-now db-migrate db-roles kb-index kb-query eval-rag push-test test-rls test-local demo trace-evals run-prod

install:
	pnpm install
	for d in $(PY_PROJECTS); do (cd $$d && uv sync) || exit 1; done

infra-up:
	$(COMPOSE) up -d

infra-down:
	$(COMPOSE) down

dev: infra-up
	(cd apps/agent && uv run python serve.py --port 8123) & \
	(cd services/mcp && uv run python -m tarangyukti.server) & \
	(cd services/channels && uv run python -m ty_channels.serve --port 8002) & \
	(cd services/worker && uv run python -m ty_worker) & \
	(cd services/copilot && node --env-file-if-exists=.env src/server.ts) & \
	(cd apps/app && npx expo start --dev-client) & \
	wait

test:
	for d in $(PY_PROJECTS); do (cd $$d && uv run pytest -q -m "not gpu and not llm") || exit 1; done
	pnpm -C apps/app test
	pnpm -C services/copilot test

lint:
	for d in $(PY_PROJECTS); do (cd $$d && uv run ruff check . && uv run ruff format --check .) || exit 1; done
	pnpm -C apps/app lint

typecheck:
	(cd packages/ty-common && uv run mypy src)
	for d in apps/agent services/mcp services/channels services/worker; do (cd $$d && uv run mypy . --exclude tests) || exit 1; done
	pnpm -C apps/app typecheck
	pnpm -C services/copilot typecheck

# ── Data (Milestone 2)
snapshot:            # capture every live source for DATE, write the SHA-256 manifest, upload to Storage
	$(MCP) tarangyukti.snapshot capture --date $(DATE) --upload

snapshot-upload:     # (re)upload an existing local snapshot
	$(MCP) tarangyukti.snapshot upload --date $(DATE)

snapshot-download:   # fetch a snapshot from Storage and verify its checksums
	$(MCP) tarangyukti.snapshot download --date $(DATE)

sim-warning:         # add the labelled SIMULATED INCOIS high-wave warning (CLEAR=1 removes it)
	$(MCP) tarangyukti.sim_warning --date $(DATE) $(if $(CLEAR),--clear,)

layers:              # rebuild data/layers from the treaty positions and WDPA
	$(MCP) tarangyukti.layers_build

# ── Knowledge base (Milestone 4)
db-migrate:          # apply supabase/migrations to SUPABASE_DB_URL (records them like the Supabase CLI)
	$(WORKER) ty_worker.migrate

db-roles:            # create/rotate ty_api, ty_worker, ty_agent and write their URLs into .env
	$(WORKER) ty_worker.db_roles

kb-index:            # Docling → chunks → Gemini Embedding 2 → kb_documents / kb_chunks (ONLY="id …" to limit)
	$(WORKER) ty_worker.kb_index $(if $(ONLY),--only $(ONLY),)

kb-query:            # make kb-query Q="fishing ban east coast"
	$(MCP) tarangyukti.rag.cli "$(Q)"

eval-rag:            # recall@8 on apps/agent/tests/golden.jsonl, appended to docs/eval-report.md
	$(MCP) tarangyukti.rag.eval --report ../../docs/eval-report.md

# ── Agent (Milestone 5)
agent:               # ty-agent on :8123 (Postgres thread memory; selector loop on Windows)
	cd apps/agent && uv run python serve.py --port 8123

agent-purge:         # delete conversation threads unused for 30 days
	$(WORKER) ty_worker.agent_purge

test-local:          # tests that call live models (Gemini) — run on the laptop, commit the report
	cd apps/agent && uv run pytest -q -m llm

# ── Simple mode (Milestone 6)
channels:            # ty-channels on :8002 (voice, brief, onboarding, push subscriptions)
	cd services/channels && uv run python -m ty_channels.serve --port 8002

push-test:           # make push-test USER=<uuid>: "alerts are on" push to every device of a user
	$(WORKER) ty_worker.push_test --user $(USER)

brief-now:           # make brief-now USER=<uuid>: send that fisher's morning brief now
	$(WORKER) ty_worker.morning --user $(USER)

i18n-draft:          # draft missing interface strings + phrase files for every language (Sarvam; status: draft)
	cd services/channels && PYTHONIOENCODING=utf-8 uv run python ../../scripts/i18n_draft.py $(if $(ONLY),--only $(ONLY),)

outbox:              # send queued pushes once
	$(WORKER) ty_worker.outbox

# ── Auth, RLS, admin (Milestone 9)
test-rls:            # cross-user row-level security tests against the dev database (test accounts)
	cd services/channels && RLS_TESTS=1 uv run pytest -q tests/test_rls.py

housekeeping:        # deletions past their 7-day undo, 30-day positions → H3 counts, 180-day answers/ledgers
	$(WORKER) ty_worker.housekeeping $(if $(DRY),--dry-run,)

failures-pull:       # admin "Add to failures dataset" → new rows in tests/failures/failures.yaml (then open a PR)
	$(WORKER) ty_worker.failures_pull

# ── Trips (Milestone 8)
sim-boat:            # simulated trip toward the border and back: GPX=path writes a GPX; POST=1 sends it to /positions
	cd services/mcp && uv run python ../../scripts/sim_boat.py $(if $(GPX),--gpx $(GPX),) $(if $(POST),--post,)

phone:       # USB phone's localhost → laptop: Metro, ty-copilot, channels, Supabase
	for p in 8081 8200 8002 54321; do adb.exe reverse tcp:$$p tcp:$$p; done

# ── Later milestones (targets reserved so the interface is stable)
# ── Deployment (Milestone 10)
demo:                # snapshot-mode demo on the laptop: every service + web build, then the smoke test
	SNAPSHOT_DATE=$(DATE) scripts/demo.sh

smoke:               # smoke test (laptop by default; CHANNELS=… COPILOT=… WEB=… for Azure)
	scripts/smoke.sh

bicep:               # validate the Azure templates (must build warning-free) — spec §16 Infra
	for f in infra/azure/*.bicep; do az bicep build -f $$f --stdout > /dev/null || exit 1; done

run-prod:            # build every image locally (Docker) the way ACR builds them
	for s in agent:apps/agent mcp:services/mcp channels:services/channels worker:services/worker; do \
	  docker build -f docker/Dockerfile.python --build-arg SERVICE_DIR=$${s#*:} -t ty-$${s%%:*}:local . || exit 1; done
	docker build -f docker/Dockerfile.copilot -t ty-copilot:local .
	pnpm -C apps/app exec expo export -p web && docker build -f docker/Dockerfile.web -t ty-web:local .

trace-evals:
	@echo "$@: Milestone 13" && exit 1
