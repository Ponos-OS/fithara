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

## Step B3 — 2026-09-13

**What changed:**
- Sharpened `CONTRIBUTING.md` item 3's `flake8-aaa` note: the Act-block heuristic's `result = ...` is literal — an assignment to any other name (e.g. `dumped = draft.model_dump(...)`) is not recognized and fails `AAA01`. `src/modules/draft/types__test.py` hit this on every round-trip test; fixed by adding `# act` comments rather than renaming to the less-descriptive `result`.
- Extracted `src.utils.CamelModel` (the alias-generator `ConfigDict` previously duplicated in `registry/models.py`, `errors.py`, and `licenses/routes.py`) since the six new draft models would have made it four-plus copies. Migrated `CanonicalLicense` and `ErrorDetail` onto it too, in a follow-up commit, rather than leaving `CONTRIBUTING.md`'s new item 16 describe a convention the existing models didn't actually follow.
- That migration surfaced a real gotcha, logged as `CONTRIBUTING.md` item 16: manually merging a subclass's `model_config` (`ConfigDict(**Parent.model_config, frozen=True)`) hits both `ruff`'s `RUF012` (dict-literal-via-unpacking reads as a mutable default) and a `pyright` overload conflict (it can't prove `frozen` isn't already in the unpacked `TypedDict`). Pydantic v2 already merges `model_config` across the inheritance chain key-by-key, so the fix was simply not merging by hand: `model_config = ConfigDict(frozen=True)` on the subclass is enough.

**Why:** All three are reusable code/tooling facts, not step-specific context — future steps will keep writing round-trip tests (hitting the `flake8-aaa` naming quirk again) and keep adding wire models (hitting the `CamelModel` question again). Recorded in `CONTRIBUTING.md` per `SELF_IMPROVE.md` step 3.

**Not generalized to `PROCESS.md`:** no step-loop issue this time — `PROCESS.md`'s existing loop (run tests, run lint, run pyright before commit) caught all three before they shipped, exactly as intended. This step also had no HTTP surface (types/rules only, not wired into `main.py`), so `rest-api-tester` was correctly skipped per the existing instruction in `PROCESS.md` step 4.

## Step B4 — 2026-09-13

**What changed:**
- Used Context7 (per the user's global instructions) to fetch pydantic-ai docs before writing `agent.py`. `resolve-library-id` listed `v2.0.0` as the latest known version, but `uv sync` actually resolved `2.43.0` — a 43-minor-version gap. Verified every API used (`Agent`, `@agent.instructions`, `@agent.tool_plain`, `.override()`, `FunctionModel`, the `"test"` model sentinel, `AgentRunError`) against the real installed version with `uv run python -c "..."` smoke tests before committing to the design; all still matched. Logged as `CONTRIBUTING.md` item 17 so this gets checked again next time, not assumed away.
- Adding the new required `Llm` settings group broke `Settings()` for every existing caller, including `GET /v1/licenses`' startup path (`main.py`'s lifespan → `get_registry()` → `get_settings()`) — there was no `.env.example` yet for `make init` to seed, so `make start_dev` would have failed on a totally unrelated route the moment `LLM__*` became required. Added `.env.example` and verified `make start_dev` + a real request to `GET /v1/licenses` both work with placeholder LLM credentials. Logged as item 18.
- `pydantic_evals`: my first `run.py` draft read `case.scores` for the custom boolean evaluator's result, which is always `{}` for a bool-returning `Evaluator` — the real pass/fail lives in `case.assertions[name].value`. Caught by manually running the evaluator against a hand-built `EvaluatorContext` before trusting it, not by any test (evals aren't part of the pytest suite by design). Logged as item 19.
- Moved `active_licenses_by_order` from `src/modules/licenses/routes.py` into `src/registry/loader.py` (and its test into `registry/loader__test.py`) since the new `list_canonical_licenses` tool needed the identical "active, ordered" filter — duplicating it in `agent.py` would have meant two copies of the same registry-shape logic living in two unrelated modules.
- No dataset `baseline.json` was fabricated: there's no `LLM__*` provider configured in this environment to produce a real eval run, so `baseline.json` is an honest placeholder (`"not_yet_run"` per case) rather than invented pass/fail data.

**Why:** All four are reusable facts about this stack/toolchain, not one-off step context — future steps will keep fetching library docs via Context7 (hitting the version-lag gap again), keep adding `Settings` fields (hitting the `.env.example` gap again if forgotten), and the evals suite will keep growing (hitting the `scores`-vs-`assertions` trap again for anyone who doesn't re-derive it empirically). Recorded in `CONTRIBUTING.md` per `SELF_IMPROVE.md` step 3.

**Not generalized to `PROCESS.md`:** no step-loop issue — the loop's existing "run tests before commit" step doesn't cover evals (they're explicitly non-blocking/non-CI per the testing philosophy), so nothing there needed to change; the gap was caught by manual verification exactly because this step's own AC called for scaffolding, not a passing suite.
