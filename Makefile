.ONESHELL:
.DEFAULT_GOAL := help
.SHELLFLAGS := -ec
.PHONY: help init start_dev start test integration_test schema evals evals_baseline evals_nightly format format_check lint_check lint clean

# Tracked and new text files, NUL separated.
TEXT_FILES = git grep --untracked -Ilz -e ''
YAML_FILES = $(TEXT_FILES) -- '*.yml' '*.yaml'
TOML_FILES = $(TEXT_FILES) -- '*.toml'
# The published docs sites are generated, so the fixers leave them as they are.
FIXABLE_FILES = $(TEXT_FILES) -- ':!docs/latest' ':!docs/v[0-9]*'
# The fixers matter for everything else, such as Markdown, YAML, JSON, the Makefile and the Dockerfile.
WHITESPACE_FIXERS = end-of-file-fixer trailing-whitespace-fixer

## Show this help message
help:
	@echo "Makefile targets:"
	@targets="$$(grep -E '^[a-zA-Z_-]+:' $(MAKEFILE_LIST) | cut -d: -f1)"; \
	width="$$(printf '%s\n' "$$targets" | awk '{ if (length > max) max = length } END { print max }')"; \
	awk -v width="$$width" ' \
		/^## / { description = substr($$0, 4); next } \
		/^[a-zA-Z_-]+:/ && description { \
			target = $$1; \
			sub(/:.*/, "", target); \
			printf "  make \033[36m%-*s\033[0m - %s\n", width, target, description; \
			description = ""; \
		} \
	' $(MAKEFILE_LIST)

## Set up the local dev environment
init:
	@command -v uv >/dev/null 2>&1 || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }
	uv sync
	npm ci
	@[ -f .env ] || { [ -f .env.example ] && cp .env.example .env; }
	npx --no-install lefthook install
	# Git opens the SSH connection before the pre-push hook runs, so a slow hook can get it dropped as idle. An existing core.sshCommand is kept.
	git config core.sshCommand > /dev/null || git config core.sshCommand "ssh -o ServerAliveInterval=30"

## Run the FastAPI app with auto-reload
start_dev:
	uv run uvicorn src.main:app --reload --port $${PORT:-8000}

## Run the FastAPI app (production mode)
start:
	uv run --no-sync uvicorn src.main:app --port $${PORT:-8000}

## Run the app with Grafana, Loki and Tempo; logs pushed over OTLP (see compose.yml)
start_stack_otlp:
	LOG_SHIPPING=otlp docker compose up --build

## Run the app with Grafana, Loki and Tempo; logs tailed from stdout by Alloy (see compose.yml)
start_stack_stdout:
	LOG_SHIPPING=stdout docker compose --profile stdout up --build

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

## Format the code
format:
	$(YAML_FILES) | xargs -0 uv run check-yaml
	$(TOML_FILES) | xargs -0 uv run check-toml
	# A fixer exits 1 after changing a file, so only a second failure is an error.
	for fixer in $(WHITESPACE_FIXERS); do
		$(FIXABLE_FILES) | xargs -0 uv run $$fixer || $(FIXABLE_FILES) | xargs -0 uv run $$fixer
	done
	uv run taplo format
	uv run ruff check --fix .
	# Colored output queries the terminal's background; inside a git hook the reply leaks into the shell.
	npx --no-install ast-grep scan --color never -U src tests
	uv run ruff format .

## Check formatting
format_check:
	$(YAML_FILES) | xargs -0 uv run check-yaml
	$(TOML_FILES) | xargs -0 uv run check-toml
	# The fixers have no check mode, so they run on a throwaway copy.
	copy="$$(mktemp -d)"
	$(FIXABLE_FILES) | tar --null -T - -cf - | tar -xf - -C "$$copy"
	for fixer in $(WHITESPACE_FIXERS); do
		$(FIXABLE_FILES) | (cd "$$copy" && xargs -0 uv run --project "$(CURDIR)" $$fixer)
	done
	uv run taplo format --check
	uv run ruff format --check .
	npx --no-install ast-grep scan src tests

## Check linters
lint_check: format_check
	uv run ruff check .
	uv run flake8
	uv run ty check
	uv run lint-imports
	npx --no-install jscpd

## Apply linters
lint: format
	uv run flake8
	uv run ty check
	uv run lint-imports
	npx --no-install jscpd

## Remove caches, venv, and build artefacts
clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
