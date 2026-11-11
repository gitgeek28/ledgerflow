# LedgerFlow task runner. Requires: Python 3.12 + uv, Node 20+, PostgreSQL 16, Tesseract. Ollama optional.
.PHONY: help setup db migrate seed fixtures demo-load reset dev api worker web test test-backend test-e2e lint evaluate evaluate-llm

help:            ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup:           ## Install backend + frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

db:              ## Create the ledgerflow role and databases in a local PostgreSQL (idempotent)
	./scripts/create_db.sh

migrate:         ## Apply database migrations
	cd backend && uv run alembic upgrade head

fixtures:        ## Regenerate synthetic invoice PDFs + scenario catalogue
	cd backend && uv run python -m app.seed.fixtures

seed:            ## Seed reference data (vendors, POs, GRNs, users, policy v1) if empty
	cd backend && uv run python -m app.seed.seed

reset:           ## Delete ALL data and reseed reference data only
	cd backend && uv run python -m app.seed.seed --reset

demo-load:       ## Reset, then build history by running the history invoices through the real pipeline
	cd backend && uv run python -m app.seed.demo_load

dev:             ## Run API (:8000), worker and web (:3000) together
	./scripts/dev.sh

api:             ## Run only the API
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app

worker:          ## Run only the background worker
	cd backend && uv run python -m app.workers.runner

web:             ## Run only the web app
	cd frontend && npm run dev

test: test-backend  ## Backend unit + integration tests (uses the ledgerflow_test database)

test-backend:
	cd backend && uv run pytest -q

test-e2e:        ## Browser end-to-end tests (needs `make dev` running; resets demo data)
	cd frontend && npx playwright test

lint:            ## Lint + type-check everything
	cd backend && uv run ruff check app tests
	cd frontend && npm run lint && npm run typecheck

evaluate:        ## Measured evaluation over the scenario catalogue -> docs/EVALUATION.md
	./scripts/evaluate.sh

evaluate-llm:    ## Same, with the local Ollama fallback enabled
	./scripts/evaluate.sh --llm
