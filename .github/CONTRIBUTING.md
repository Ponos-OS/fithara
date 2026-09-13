# Contributing to `fithara`

Thanks for helping out. This document covers the project layout and the testing philosophy so you know **which kind of test to write for what**.

## How to Start on Local Machine

- [`uv`](https://docs.astral.sh/uv/).

```shell
make init
make start_dev
```

No database, queue, or object store — the service is stateless (§0.4/§4.7 of `REQUIREMENTS.md`), so there's nothing to run in Docker for local dev. [Docker](https://www.docker.com/) is only needed to build the production image (`Dockerfile`, Step B8).

## Project Structure

Modular by feature, mirroring the sibling project `smart-novel-beatrice`: one directory per feature under `modules/`, self-contained (routes, agent, types, prompts, evals, tests colocated). Cross-cutting concerns (config, the canonical license registry) live outside `modules/`, the same way `beatrice` keeps `src/utils/` outside its `src/modules/`.

Every package (`src/`, `src/utils/`, `src/registry/`, `src/modules/licenses/`, ...) has an `__init__.py` that is a **barrel**: it re-exports that package's public API and nothing else, so callers write `from src.utils import Settings, get_settings` instead of reaching into the submodule that happens to define them (`from src.utils.config import Settings`). This is enforced, not just convention — see the `TID251`/banned-api note in the Design & Code Philosophy section below. A symbol stays out of the barrel (and out of `__all__`) when it's genuinely internal to the package, e.g. `active_licenses_by_order`/`find_license_or_error` in `src/modules/licenses/routes.py`, which only that module's own `routes__test.py` should reach for directly.

```
fithara/
├── src/
│   ├── __init__.py                    # Package marker; no exports (this is the app, not a library)
│   ├── main.py                        # FastAPI app factory — only place routers are wired together (no side effects on import, see `make schema`)
│   ├── utils/                         # Cross-cutting concerns shared by every module — never LLM/business logic
│   │   ├── __init__.py                # Barrel: re-exports Settings, get_settings, CamelModel, ErrorResponse, api_error, ...
│   │   ├── api_model.py               # CamelModel — shared snake_case⇄camelCase BaseModel base for every wire model
│   │   ├── config.py                  # Settings / get_settings() — pydantic-settings (§4.8)
│   │   ├── config__test.py            # Unit tests: required fields, defaults, nested __ env vars
│   │   └── errors.py                  # §4.10 error envelope (ErrorResponse) + api_error() helper
│   ├── registry/                      # Canonical license registry (§3) — shared by both modules below
│   │   ├── __init__.py                # Barrel: re-exports CanonicalLicense, load_registry, get_registry, RegistryLoadError
│   │   ├── loader.py                  # Parses Markdown + YAML frontmatter from licenses/
│   │   ├── loader__test.py            # Unit tests: valid/invalid files, unique IDs, boot-time failure
│   │   └── models.py                  # CanonicalLicense Pydantic model
│   ├── modules/
│   │   ├── __init__.py                # No exports — just a namespace for feature packages, mirrors beatrice
│   │   ├── licenses/                  # Feature: browsing the canonical registry over HTTP
│   │   │   ├── __init__.py            # Barrel: re-exports router, LicenseSummary, LicenseDetail, LicenseListResponse
│   │   │   ├── routes.py              # GET /v1/licenses, GET /v1/licenses/{id} (404/410 semantics, §4.10)
│   │   │   └── routes__test.py        # Unit tests against a fixture registry, no HTTP server
│   │   └── draft/                     # Feature: the conversational drafting endpoint
│   │       ├── routes.py              # POST /v1/draft — thin, delegates to agent.py
│   │       ├── types.py               # Draft, DraftSource, ConversationTurn, DraftRequest/Response
│   │       ├── types__test.py         # Serialization round-trips
│   │       ├── rules.py               # Rules 1–6 as pure validators (§4.5), independent of any LLM call
│   │       ├── rules__test.py         # Unit tests for the draft-mutation rules
│   │       ├── agent.py               # PydanticAI agent, tools, structured output (§4.6)
│   │       ├── agent__test.py         # Unit tests with the LLM call mocked out
│   │       ├── prompts/
│   │       │   └── v1.md              # System prompt — version-controlled, counsel-reviewed (see Prompt Versioning)
│   │       └── evals/
│   │           ├── run.py             # Entrypoint invoked by `make evals`
│   │           ├── dataset.yaml       # Eval cases + expected metadata
│   │           ├── baseline.json      # Committed pass/fail matrix — the source of truth
│   │           └── report.json        # Last eval run output (regenerated each run)
│   └── licenses/                      # Canonical license Markdown files (§3.1), loaded read-only at startup
│       ├── _schema.json               # Frontmatter schema — enforced at boot
│       ├── ALL-RIGHTS-RESERVED.md
│       ├── CC-BY-4.0.md
│       ├── CC-BY-SA-4.0.md
│       ├── CC-BY-NC-4.0.md
│       └── CC-BY-NC-SA-4.0.md
├── tests/                             # Integration tests — schema/contract conformance only, LLM stubbed (§4.11)
│   ├── conftest.py                    # Fixtures: test app, stubbed agent, fixture registry dir
│   ├── test_licenses_endpoints.py     # GET /v1/licenses, GET /v1/licenses/{id}
│   ├── test_draft_endpoint.py         # POST /v1/draft — response shape + rule-derived invariants
│   └── test_prompt_injection.py       # Injection corpus → schema-valid, rule-compliant fallback
├── docs/
│   └── openapi.json                   # Generated by `make schema`; committed; source of truth for hosted docs (Part 5)
├── Dockerfile                         # Backend image (Step B8 / Part 5)
├── Makefile                           # Single entry point — see §4.13; no ad-hoc `uv run ...` invocations
├── pyproject.toml                     # uv-managed dependencies + project metadata
└── uv.lock                            # Committed lockfile
```

- **Unit tests** are colocated with the source they cover, using the `*__test.py` suffix, and live under `src/`. `make test` runs `uv run pytest src/ -v`.
- **Integration tests** live only under `tests/` and are run via `make integration_test` (`uv run pytest tests/ -v`) — a separate pytest invocation over a separate tree.
- **A new feature is a new directory under `src/modules/`.** If it needs its own routes, LLM agent, or prompts, give it its own `routes.py`/`agent.py`/`types.py`/`prompts/` — don't grow `licenses/` or `draft/` to cover unrelated concerns.
- `docs/openapi.json` is a **generated, committed artefact**. Regenerate it with `make schema` whenever routes or models change; CI fails if it's stale.

## Testing Philosophy

Three tiers. Each answers a different question. Put each new test in the tier that matches what you actually want to verify.

1. Unit tests:
   - **Question:** _Does this piece of Python behave correctly in isolation?_
   - Fast, hermetic, no network, no live LLM.
   - Test whatever is easy and worthwhile to unit test: pure functions, type validation, route logic with the agent mocked out, error mapping, prompt-template rendering, the Rule 1–6 validators, etc.
   - If a test needs a live LLM to make sense, it is **not** a unit test — move it to evals. Integration tests stub the LLM too (see below); a live LLM never runs in CI.
   - Add unit tests generously. They are cheap.
   - Mock the LLM call at the module boundary (the PydanticAI agent call in `agent.py`) rather than hitting a real provider.
2. Integration tests:
   - **Question:** _Do the HTTP endpoints actually work end-to-end against the running app?_
   - Spin up the FastAPI app in-process (e.g. `httpx.ASGITransport`/`TestClient`) with the LLM agent stubbed to return fixed, known structured output, hit the endpoint over HTTP, assert on the response shape and rule-derived invariants — never on `assistantMessage` wording or other LLM-authored text (§4.11).
   - Purposefully thin — one happy-path per endpoint per `source.type` variant, plus the documented error paths (`404`/`410`/validation).
   - No external infra (no database, queue, or object store — the service is stateless), so no Testcontainers are needed here; a fixture registry directory and a stubbed agent are enough.
   - Add an integration test when introducing a new endpoint or when a bug regressed the request/response contract.
3. Evals:
   - **Question:** _Are the prompts producing outputs that satisfy our rules? Is the model still doing what we expect?_
   - Use [`pydantic-evals`](https://ai.pydantic.dev/evals/) to run each module's dataset against the live LLM and score each row with a set of structural evaluators.
   - Catch:
     - Prompt edits that unintentionally degrade output quality.
     - Model changes (swapping providers/models) that shift behaviour.
     - Rule violations that unit tests can't express because they depend on natural-language output.

### When `make evals` Fail

**Genuine regression** (unintended): fix the prompt / code and re-run until the baseline passes again.

**Deliberate quality change** (you improved the prompt on purpose, or intentionally changed the model / temperature / rules): review the new `report.json` values, then commit the new baseline with: `make evals_baseline`

**Commit the updated baselines in the same PR as the change that caused them**, with a short justification in the commit message.

## Prompt Versioning

Prompts live at `src/modules/<module>/prompts/v1.md` (or `v1.jinja2` if a module needs per-request templating rather than a static system prompt). The question that decides whether a change updates that file in place or ships as `v2.md` is: **does this change what "correct output" means for existing callers/evals?**

- **Update the existing version in place** when the prompt wasn't honoring its own contract — a bug fix, a flaky-output fix, a wording/clarity tweak — and `dataset.yaml`'s expectations don't need to change. The fix should converge back to the existing `baseline.json`, not require redefining it.
- **Create a new version** (`v2.md`, etc.) when you're intentionally changing behavior: new/removed rules, different drafting semantics, a model swap, or a rewrite where the old prompt isn't a strict subset/superset of the new rules. Also reach for a new version when you need to A/B the old and new prompt, or when rollback needs to be trivial (keep both files rather than relying on git history).
- Signal to double check yourself: if fixing a bug required editing expected values in `dataset.yaml` beyond just making a previously-flaky case pass, that's evidence the change was actually behavioral and should have been a new version.

## Design & Code Philosophy

1. Simpler is better - **do not overcomplicate**.
2. Prefer **early returns over nested conditionals**.
3. Use pytest.
   - Use [AAA (Arrange, Act, Assert) style of writing test](https://stackoverflow.com/tags/arrange-act-assert/info).
   - [`flake8-aaa`](https://pypi.org/project/flake8-aaa/) (`make lint_check` / `make lint`, config in `.flake8`) checks AAA structure via AST — it identifies the Act block semantically (a `result = ...` assignment, `with pytest.raises(...)`, or a `# act` comment) rather than counting blank lines, and is Black/ruff-format-compatible. "`result = ...`" is literal: an assignment to any other name (`dumped = draft.model_dump(...)`, `response = await client.get(...)`) is **not** recognized as the Act block and fails `AAA01`. Either name the variable `result`, or — when a more descriptive name reads better (as it usually does) — add a trailing `# act` comment on that line instead of renaming it.
   - **Known gap, confirmed against 0.17.2 (latest on PyPI):** it only checks `def test_...`, not `async def test_...` — there's no `AsyncFunctionDef` handling in its visitor at all, so it silently skips async tests entirely. Since this suite runs under `asyncio_mode = auto` and most tests are async, a clean `flake8-aaa` run is not proof of AAA compliance — it's only checking whatever sync test functions exist. Review async tests for AAA by eye; the violation this misses most often is an `assert` buried inside a mock/stub closure defined in the Arrange block (asserting on the request payload from inside the `httpx.MockTransport` handler, for example) instead of pulled out into the Assert block.
4. IMPORTANT: Avoid overly defensive programming; avoid `insistence` checks; only manage exceptions when necessary.
5. Use `uv`; ALWAYS `uv run xxx` NEVER `python3 xxx`.
6. Use latest version of libraries and idiomatic approaches as of today.
7. Class owning an `httpx.AsyncClient` → see the `httpx-async-transport` skill.
8. An enum/type that a module needs _and_ that `Settings` needs to reference (e.g. to pick which of that module's implementations to use) belongs in `src/utils/config.py`, colocated with the other settings enums, not in the module itself. `Settings` is imported nearly everywhere, so defining that type in the module instead creates a straight import cycle the moment `Settings` needs it too.
9. Comma-separated / delimited env var on a `BaseSettings` field → see the `settings-list-env-field` skill.
10. Asserting on `extra={...}` log fields via `caplog` → see the `caplog-extra-typing` skill.
11. `pytest` resolving `src.*` imports in `*__test.py` files needs `[tool.pytest.ini_options] pythonpath = ["."]` in `pyproject.toml` — without it, pytest's rootdir-based discovery doesn't add the repo root to `sys.path` and every colocated unit test fails to collect with `ModuleNotFoundError: No module named 'src'`.
12. This service is an application, not a distributable library, and `src/` isn't a package meant for `uv`'s build backend to install — set `[tool.uv] package = false` in `pyproject.toml` so `uv sync` doesn't try to build/install the project itself as a package (which fails without a matching package directory for the build backend to find).
13. A nested settings group under `Settings` (e.g. `Registry`, `Llm`) must be a plain `pydantic.BaseModel`, not `BaseSettings`. A nested `BaseSettings` is itself an independent settings source: it reads the *whole* process environment case-insensitively, so a field like `Registry.path` silently binds to the ubiquitous `PATH` env var instead of only the `REGISTRY__PATH` slice `Settings.env_nested_delimiter` carves out for it. Only the outermost `Settings` class should subclass `BaseSettings`.
14. FastAPI's default handler for `HTTPException` wraps whatever you pass as `detail` inside `{"detail": ...}` — so raising `HTTPException(status_code=404, detail={"error": {...}})` (the §4.10 error envelope) actually serves `{"detail": {"error": {...}}}`, not the documented flat `{"error": {...}}` shape. Register an app-level `@app.exception_handler(HTTPException)` that returns `JSONResponse(status_code=exc.status_code, content=exc.detail)` so `exc.detail` is served verbatim as the response body.
15. **Barrel imports are enforced, not just conventional.** Every package's `__init__.py` re-exports its public API (see the project-structure tree above); importing a symbol from the submodule that actually defines it instead of the package barrel (e.g. `from src.utils.config import Settings` instead of `from src.utils import Settings`) is a lint error, not a style nit. This is `ruff`'s `flake8-tidy-imports` banned-api rule (`TID251`), configured in `pyproject.toml`'s `[tool.ruff.lint.flake8-tidy-imports.banned-api]` table — one `"pkg.submodule".msg = "..."` entry per submodule that a barrel exists for. Two things to remember when adding a new barrel package:
    - Add the new `"pkg.submodule"` ban entry, and add a `per-file-ignores` entry for the new `__init__.py` itself (it has to import from its own submodules) and for `<submodule>.py` files that import a *sibling* submodule within the same package (e.g. `src/registry/loader.py` importing `src/registry/models.py`).
    - A symbol that's genuinely private to a submodule (not part of the package's public API) is not exported from the barrel, and a test that needs it imports the submodule directly — add that test file to `per-file-ignores` too, with a one-line comment on *why* it's an exception (see `src/modules/licenses/routes__test.py`'s entry).
16. Every wire model (a request/response Pydantic model exposed over HTTP) should subclass `src.utils.CamelModel`, not redefine its own `alias_generator=AliasGenerator(validation_alias=to_camel, ...)` `ConfigDict`. Pydantic v2 merges `model_config` across the inheritance chain key-by-key (it's not a plain class attribute that gets fully overridden) — so a subclass needing extra config (e.g. `CanonicalLicense`'s `frozen=True`) just writes `model_config = ConfigDict(frozen=True)`; the parent's `alias_generator`/`populate_by_name` survive without being repeated or merged by hand.
17. When Context7 resolves a library, the versions it lists (e.g. pydantic-ai's `v2.0.0`) can lag well behind what `uv add`/`uv sync` actually resolves from PyPI (it resolved `2.43.0` for the same query) — Context7's docs are a starting point, not proof the API still looks like that. Before writing real code against fetched docs, smoke-test the actual imports/calls in `uv run python -c "..."` against the installed version; don't assume a multi-version gap means the API is unchanged.
18. Adding a new *required* field/group to `Settings` (no default) breaks `get_settings()` for every caller, not just the feature that needed it — `main.py`'s startup lifespan calls `get_registry()`, which calls `get_settings()`, so an unrelated route (e.g. `GET /v1/licenses`) stops starting up if a new required `Llm.api_key` is missing. Whenever a step adds a required `Settings` field, also add/update `.env.example` with a placeholder value so `make init` → `make start_dev` keeps working out of the box.
19. `pydantic_evals`: a custom `Evaluator.evaluate` that returns a plain `bool` (or a `dict[str, bool]`) shows up on `EvaluationReportCase.assertions` (a `dict[str, EvaluationResult]`, read the pass/fail via `.value`), **not** `.scores` — `.scores` stays `{}` for boolean evaluators and is only populated by evaluators that return a numeric `EvaluationScore`. Confirmed empirically against the installed version; the two are easy to conflate since both cases render as ordinary report columns.
20. A `Settings()` test asserting "field X is absent/uses its default" must construct it as `Settings(_env_file=None)`, not bare `Settings()` — `monkeypatch.delenv(...)` only clears the process environment, not pydantic-settings' separate `.env`-file source, so the test passes or fails depending on whether the developer happens to have run `make init` locally (which creates a real `.env`). `_env_file=None` isn't in `BaseSettings`'s generated `__init__` signature, so pyright needs `# pyright: ignore[reportCallIssue]` on that line.
21. A FastAPI dependency function used only via `dependencies=[Depends(fn)]` (not as a route handler itself, e.g. `enforce_rate_limit`) doesn't get `ruff`'s built-in B008 exemption for `Depends(...)` in its own sub-dependencies' defaults when any parameter's type annotation is a subscripted generic (`Agent[None, X]`, `list[int]`, `dict[str, int]` — plain `tuple[X, ...]` is fine, oddly). This is a `ruff` false positive, not a real issue — fixed once, project-wide, via `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls = ["fastapi.Depends"]` in `pyproject.toml`, rather than annotating around it per call site.
22. `Agent("openai:gpt-5.2")` (a bare model string) makes PydanticAI build its own provider client from that provider's *conventional* env var (`OPENAI_API_KEY`, etc.) — it silently ignores any explicit key you have in `Settings`, even one named `Llm.api_key` and validated as required. A `Settings`-sourced key only actually gets used if you build the `Provider` yourself: `infer_provider_class(settings.provider)(api_key=settings.api_key)`, then `infer_model(f"{provider}:{model}", provider_factory=lambda _: provider)`. Caught by manually running `make start_dev` and hitting the route for real — none of the mocked-model unit tests would ever exercise this path, since they never go through `get_agent()`/real settings at all.
23. **A FastAPI dependency override lambda must close over a pre-built instance, not construct one inline** (`instance = Thing(); app.dependency_overrides[get_thing] = lambda: instance`, never `app.dependency_overrides[get_thing] = lambda: Thing()`) whenever the dependency is stateful (a counter, a cache, anything meant to accumulate across requests within one test). FastAPI calls an override fresh on every dependency resolution with no caching of its own — `lambda: Thing()` silently hands each request its own object, so a rate limiter "reset" to a fresh empty counter every single call and a 429 test passed 200 twice before this was caught by actually running it.
24. A custom exception handler for `RequestValidationError` must build the client-facing message from `exc.errors()` (structured, safe), never `str(exc)` — the latter includes an internal traceback fragment (source file path, line number, function name) that leaks server implementation details into an API response. Caught by `rest-api-tester`'s manual verification, not by any unit test (nothing asserts on the exact error message text).
25. A route handler must never call `get_settings()` (or read any of its nested groups) directly in its own body — wrap it in a small dependency function (`def get_conversation_limits() -> Conversation: return get_settings().conversation`) and take it via `Depends(...)`, matching `get_registry`/`get_agent`/`get_rate_limiter`. Calling `get_settings()` inline broke every existing `POST /v1/draft` integration test the moment it shipped: those tests stub `get_agent`/`get_rate_limiter` and never populate the real (LLM-key-requiring) `Settings` singleton, so the first uncached `get_settings()` call in the request path raised `ValidationError` instead of using the test's fixtures. If a route needs a config value, it needs a `Depends`-wrapped accessor for it, full stop — no exceptions for "it's just one value."
