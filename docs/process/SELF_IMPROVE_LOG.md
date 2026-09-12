# Self-Improvement Log

## Step B1 — 2026-09-13

**What changed:** Added two reusable `pyproject.toml` gotchas to `.github/CONTRIBUTING.md`'s Design & Code Philosophy (items 11-12): `pythonpath = ["."]` is required for colocated `*__test.py` imports of `app.*` to resolve, and `[tool.uv] package = false` is required since this is an application without a `src/<package>/` layout. Also fixed stray leftover XML-like markup (`</content></invoke>`) at the end of `CONTRIBUTING.md` from a prior edit mistake.

**Why:** Nothing in the repo existed yet — no `pyproject.toml`, `uv.lock`, or working `Makefile` targets — so Step B1 required bootstrapping the whole project via `uv init` before the registry loader could be written and tested. Both gotchas surfaced immediately (`ModuleNotFoundError` on first `make test`, and would have hit a build-backend error on `uv sync` had the default `uv init` package layout been kept). These are one-time project-setup facts but the code pattern (pytest config, uv config) is reusable knowledge for anyone re-bootstrapping a similar service, so they went to `CONTRIBUTING.md` per `SELF_IMPROVE.md` step 3, not `PROCESS.md` (which is about the step loop, not code/config patterns).

**Not generalized to `PROCESS.md`:** the "bootstrap the project" work itself was a one-off (only the very first step in a repo needs it) — no process change made from a single data point, per `SELF_IMPROVE.md` step 2's guidance.
