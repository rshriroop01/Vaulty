# Vaultly — every workflow goes through make. `make help` lists targets.
.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: ## First-time setup: env file + git hooks
	cp -n .env.example .env || true
	pre-commit install

dev: ## Start the entire stack (web, api, worker, beat, postgres, redis, minio, mailpit)
	docker compose up --build

down: ## Stop the stack
	docker compose down

logs: ## Tail all service logs
	docker compose logs -f

test: test-api test-web ## Run all tests

test-api: ## Backend tests with coverage gate (>=80%)
	cd apps/api && python -m pytest

test-web: ## Frontend tests
	cd apps/web && npm test

lint: ## Lint everything
	cd apps/api && ruff check . && ruff format --check .
	cd apps/web && npm run lint && npm run format:check

format: ## Auto-format everything
	cd apps/api && ruff check --fix . && ruff format .
	cd apps/web && npm run format

typecheck: ## Static type checks (mypy strict + tsc)
	cd apps/api && mypy app
	cd apps/web && npm run typecheck

migrate: ## Create a migration: make migrate m="add documents table"
	docker compose run --rm api alembic revision --autogenerate -m "$(m)"

upgrade: ## Apply migrations
	docker compose run --rm api alembic upgrade head

types: ## Regenerate TS types from the running API's OpenAPI contract
	cd packages/shared-types && npm run generate

db-shell: ## psql into the local database
	docker compose exec postgres psql -U vaultly vaultly

.PHONY: help setup dev down logs test test-api test-web lint format typecheck migrate upgrade types db-shell
