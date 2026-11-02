# TarangYukti Makefile (spec Annexure B). Runs in bash: WSL, Git Bash or CI.
-include .env
export

PY_PROJECTS := packages/ty-common apps/agent services/mcp services/channels services/worker
COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml

.PHONY: install infra-up infra-down dev test lint typecheck phone \
        snapshot snapshot-upload layers kb-index kb-query push-test test-rls test-local eval-rag demo trace-evals run-prod

install:
	pnpm install
	for d in $(PY_PROJECTS); do (cd $$d && uv sync) || exit 1; done

infra-up:
	$(COMPOSE) up -d

infra-down:
	$(COMPOSE) down

dev: infra-up
	(cd apps/agent && uv run uvicorn server:app --port 8123 --reload) & \
	(cd services/mcp && uv run python -m tarangyukti.server) & \
	(cd services/channels && uv run uvicorn ty_channels.app:app --port 8002 --reload) & \
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

phone:       # USB phone's localhost → laptop: Metro, ty-copilot, channels, Supabase
	for p in 8081 8200 8002 54321; do adb.exe reverse tcp:$$p tcp:$$p; done

# ── Later milestones (targets reserved so the interface is stable)
snapshot snapshot-upload layers:
	@echo "$@: Milestone 2" && exit 1
kb-index kb-query eval-rag:
	@echo "$@: Milestone 4" && exit 1
test-local:
	@echo "$@: Milestone 5" && exit 1
push-test:
	@echo "$@: Milestone 6" && exit 1
test-rls:
	@echo "$@: Milestone 9" && exit 1
demo run-prod:
	@echo "$@: Milestone 10" && exit 1
trace-evals:
	@echo "$@: Milestone 13" && exit 1
