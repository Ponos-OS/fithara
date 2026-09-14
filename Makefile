.DEFAULT_GOAL := help

## Show this help
help:
	@awk 'BEGIN {FS = ":.*##|## "} /^[a-zA-Z_-]+:.*?## |^## /{if ($$0 ~ /^##/) {print "\n" $$2} else {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}}' $(MAKEFILE_LIST)

## Set up the local dev environment (.venv, deps, .env)
init:
	@command -v uv >/dev/null 2>&1 || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }
	uv sync
	@[ -f .env ] || { [ -f .env.example ] && cp .env.example .env; }
	uv run pre-commit install || true

## Run the FastAPI app with auto-reload
start_dev:
	uv run uvicorn src.main:app --reload --port $${PORT:-8000}

## Run the FastAPI app (production mode)
start:
	uv run --no-sync uvicorn src.main:app --port $${PORT:-8000}

## Run unit tests (src/**/*__test.py)
test:
	@echo "== unit tests: $$(date -u +%FT%TZ) =="
	uv run pytest src/ -v
	@echo "== unit tests done: $$(date -u +%FT%TZ) =="

## Run integration tests (tests/)
integration_test:
	@echo "== integration tests: $$(date -u +%FT%TZ) =="
	uv run pytest tests/ -v
	@echo "== integration tests done: $$(date -u +%FT%TZ) =="

## Export the OpenAPI schema to docs/openapi.json (source of truth for API docs)
schema:
	@echo "== exporting OpenAPI schema to docs/openapi.json =="
	mkdir -p docs
	uv run python -c "import json; from src.main import app; f = open('docs/openapi.json', 'w'); json.dump(app.openapi(), f, indent=2); f.write('\n')"
	@echo "== wrote docs/openapi.json =="

## Run the draft agent's golden-scenario evals against a live LLM (non-blocking, needs LLM__* configured)
evals:
	uv run python -m src.modules.draft.evals.run

## Promote the last `make evals` report.json to the committed baseline.json
evals_baseline:
	cp src/modules/draft/evals/report.json src/modules/draft/evals/baseline.json

## Run evals against a real, Testcontainers-managed Ollama (nightly CI; needs Docker + the `evals` dep group)
evals_nightly:
	uv run --group evals python local-setup/ollama/run_nightly_evals.py

## Check lint/format/types/import-architecture without mutating files (CI)
lint_check:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright
	uv run lint-imports

## Apply lint/format fixes and check types + import architecture (local dev)
lint:
	uv run ruff format .
	uv run ruff check --fix .
	uv run pyright
	uv run lint-imports

## Remove caches, venv, and build artefacts
clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache .pyright build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

.PHONY: help init start_dev start test integration_test schema evals evals_baseline evals_nightly lint_check lint clean
