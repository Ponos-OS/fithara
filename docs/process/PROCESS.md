## Developing Features Process

`REQUIREMENTS.md` is split into independently-committable steps. Work ONE step per pass through this loop.

1. Check `git log` / the current code to find the next unimplemented step in `REQUIREMENTS.md`. Do not redo a step that's already merged, and do not start a later step early just because it's convenient.
2. Build only that step's scope.
3. Add tests at the tier `.github/CONTRIBUTING.md` calls for (unit for pure logic/route logic with the agent mocked, integration for a new/changed HTTP endpoint, evals for prompt changes). Each step's "Tests" subsection in `REQUIREMENTS.md` says which tiers apply and whether `rest-api-tester` is relevant.
4. If the step exposes or changes an HTTP endpoint's request/response contract, invoke the `rest-api-tester` subagent with: the endpoint(s) (method + path), their file path, and the step's AC. Skip this for steps with no HTTP surface (e.g. registry-loader-only or rules-only steps) — invoking it with nothing new to test wastes the call. This service has no database/queue/object store (§0.4 of `REQUIREMENTS.md`), so a dev server is just `make start_dev` — no `docker compose` needed. Tear the dev server down after. After launching the subagent, don't spawn another agent just to "wait" — the completion notification arrives on its own; stop and let the turn end.
   - Warn the user if a step's `### Tests` subsection says to skip `rest-api-tester` or skip unit testing.
5. Incorporate whatever `rest-api-tester` or the test suite surfaces.
   - Integration tests (`tests/`) are schema/contract conformance only (§4.11) — never assert on `assistantMessage` wording or other LLM-authored text. If a step's `### Tests` subsection seems to ask for that, cover the behavior at the unit tier against `rules.py`/a mocked agent instead, and say so in the test file.
6. Run `make evals` if any `app/modules/*/prompts/*.md` (or `.jinja2`) file changed; if the regression is deliberate, commit the updated baseline per `.github/CONTRIBUTING.md` (`make evals_baseline`).
   - When a step's `### Tests` says to verify manually (no pytest tier — e.g. Makefile/CI plumbing), actually run that verification rather than treating the AC as sufficient on paper. When it surfaces a real gap, fix it and update `REQUIREMENTS.md`'s AC for that step to match reality.
   - A `### Tests` claim that an _existing_ test "should still pass unmodified" is a guess, not a fact — run it before believing it. When it doesn't hold, update that test's fixtures/stubs to the new contract rather than treating the claim as the AC.
7. If the step changes a Pydantic field's `description=...`, a route's `responses=`, or anything else that shapes the OpenAPI schema, run `make schema` before committing — `docs/openapi.json` is generated, not hand-edited, and won't reflect the new wording otherwise.
8. Commit the step on its own, with a message naming the `REQUIREMENTS.md` step number.
   - A pre-commit hook (if configured) runs the full unit suite (`make test`) and blocks the commit on any failure — so if this step removes/renames something a later step's file still references (e.g. a settings field), fold the minimal fix to that other file into this commit rather than leaving it red until the next step.
9. IMPORTANT: follow the instructions in `SELF_IMPROVE.md` to improve yourself.

You MUST complete step 9 (self-improvement) before you stop.
