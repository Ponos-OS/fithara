## Project Summary

A stateless, LLM-assisted Python service exposing a **REST API** that helps users pick and draft a content license for a written work, from a curated registry of canonical licenses.

## Standards & Guidelines

@.github/CONTRIBUTING.md

- Comments only when necessary, this includes docstrings; don't add one just to restate what the name/code already say.
- Exception: wire models (FastAPI `response_model`/request bodies) get a class docstring and `Field(description=..., examples=[...])` on non-obvious fields — these land in the OpenAPI docs, so they're not "restating code." Do this by default, unasked. Docstring describes what the model *is* ("The assistant's reply to a draft turn"), never "Request/Response body for `METHOD /path`" — that duplicates the route wiring, drifts out of sync when routes move, and can't be linted for staleness. Examples go on the field itself (`Field(examples=["CC-BY-NC-4.0"])`, Pydantic v2's real mechanism — not the deprecated Pydantic v1 `example=` singular kwarg some tutorials still show), never as a shared module-level dict merged into multiple models' `model_config` — that's the same "two places to keep in sync" problem as the docstring rule above, just moved into data instead of prose. Reach for a model-level `model_config = ConfigDict(json_schema_extra={"examples": [...]})` full-object example only when the fields' relationship to each other is the point (e.g. a conversation history that needs to read as one coherent exchange) and per-field examples can't show that.
- Be concise, short README, no emojis.
- No extra feature, focus on what has been asked.
- `BaseSettings` with a discriminator picking between interchangeable implementations (e.g. `Tts.default_provider`) → only the selected implementation's fields are required; enforce that via a `model_validator` on the parent, not a bare required field on each implementation.
- Never cite a `REQUIREMENTS.md` section number (`§3.3`, `§4.10`, "Step B2", ...) in a comment, docstring, or commit message body meant to explain the code itself. `REQUIREMENTS.md` is archived and deleted once the feature ships (see Development Process below), so a `§`-reference in source code becomes a dead pointer the moment that happens. Explain the *why* in the comment itself instead, in terms that stay true without the spec present.

## Development Process

Each feature is built incrementally against a `REQUIREMENTS.md` at the repo root, split into steps meant to be implemented, tested, and committed one at a time — see `docs/process/PROCESS.md` for the per-step loop and `docs/process/SELF_IMPROVE.md` for the required wrap-up. `REQUIREMENTS.md` and the per-feature self-improvement log are archived (e.g. to a GitHub issue) and removed once the feature ships; a new `REQUIREMENTS.md` is written per feature.
