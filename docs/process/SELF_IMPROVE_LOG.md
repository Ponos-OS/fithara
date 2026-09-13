# Self-Improvement Log

## Step B1 — 2026-09-13

**What changed:** Added two reusable `pyproject.toml` gotchas to `.github/CONTRIBUTING.md`'s Design & Code Philosophy (items 11-12): `pythonpath = ["."]` is required for colocated `*__test.py` imports of `app.*` to resolve, and `[tool.uv] package = false` is required since this is an application without a `src/<package>/` layout. Also fixed stray leftover XML-like markup (`</content></invoke>`) at the end of `CONTRIBUTING.md` from a prior edit mistake.

**Why:** Nothing in the repo existed yet — no `pyproject.toml`, `uv.lock`, or working `Makefile` targets — so Step B1 required bootstrapping the whole project via `uv init` before the registry loader could be written and tested. Both gotchas surfaced immediately (`ModuleNotFoundError` on first `make test`, and would have hit a build-backend error on `uv sync` had the default `uv init` package layout been kept). These are one-time project-setup facts but the code pattern (pytest config, uv config) is reusable knowledge for anyone re-bootstrapping a similar service, so they went to `CONTRIBUTING.md` per `SELF_IMPROVE.md` step 3, not `PROCESS.md` (which is about the step loop, not code/config patterns).

**Not generalized to `PROCESS.md`:** the "bootstrap the project" work itself was a one-off (only the very first step in a repo needs it) — no process change made from a single data point, per `SELF_IMPROVE.md` step 2's guidance.

## Step B2 — 2026-09-13

**What changed:**
- Introduced `src/utils/` (config.py, config__test.py, errors.py) mid-step at the user's explicit request, moving cross-cutting config/error code out of top-level `src/`. Updated `REQUIREMENTS.md` and `CONTRIBUTING.md`'s project-layout trees and prose to match, including §4.8's location pointer.
- While fixing those docs, found and fixed a real bug in §4.8's own `Settings` code sample: `Llm`, `Registry`, `Conversation`, `RateLimit` were declared as `BaseSettings` instead of `BaseModel`. A nested `BaseSettings` reads the whole process environment independently and case-insensitively, so `Registry.path` was silently binding to the ambient `PATH` env var instead of `REGISTRY__PATH` — caught by `config__test.py`'s default-value assertion failing with `PATH`'s actual value. Fixed in both the implementation and the spec sample; logged as CONTRIBUTING.md item 13.
- Added CONTRIBUTING.md item 14: FastAPI's default `HTTPException` handler wraps `detail` in `{"detail": ...}`, so matching the flat §4.10 `{"error": {...}}` envelope needs an app-level `exception_handler(HTTPException)` override returning `JSONResponse(exc.status_code, exc.detail)` directly. Caught by the integration tests (`tests/test_licenses_endpoints.py`) failing on a `KeyError: 'error'`.
- Fixed `make schema`'s `python -c` one-liner to write a trailing newline — without it, the `openapi-schema` pre-commit hook (which reruns `make schema` last) and the `end-of-file-fixer` hook (which runs earlier) fought each other every commit, each undoing the other's fix.

**Why:** All three code-pattern gotchas (nested `BaseSettings`, FastAPI's `HTTPException` wrapping, and the schema-hook newline fight) are reusable facts about this stack, not one-off step context — future steps (B4's `Llm` settings, B5's `RateLimit`/`Conversation` settings, any new endpoint using `api_error()`) would hit the same traps again. Recorded in `CONTRIBUTING.md` per `SELF_IMPROVE.md` step 3; the Makefile fix needed no doc entry since the corrected command is self-evidently right on inspection.

**Not generalized to `PROCESS.md`:** all three are code/config-pattern issues, not step-loop issues — `PROCESS.md`'s existing loop already caught them (via `config__test.py` and the integration suite) before commit, exactly as intended.
