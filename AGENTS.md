## Project Summary

A stateless, LLM-assisted Python service exposing a **REST API** that helps users pick and draft a content license for a written work, from a curated registry of canonical licenses.

## Standards & Guidelines

@.github/CONTRIBUTING.md

- Comments only when necessary, this includes docstrings; don't add one just to restate what the name/code already say.
- Exception to the rule above: every wire model (a Pydantic model used as a FastAPI `response_model` or request body) gets a class docstring, plus `Field(description=...)` on every field whose meaning isn't fully carried by its name and type alone (skip it on truly self-evident fields like `role: Literal["user", "assistant"]`). These aren't internal comments — FastAPI puts them straight into the generated OpenAPI schema and hosted docs, so they're user-facing documentation for whoever integrates against the API, not restated code. Add a realistic full-object example too, via `model_config = ConfigDict(json_schema_extra={"examples": [...]})`, on any request/response model substantial enough that one clarifies the shape (skip it on trivial one-or-two-field models). Do this without being asked, for every new or edited wire model.
- Be concise, short README, no emojis.
- No extra feature, focus on what has been asked.
- `BaseSettings` with a discriminator picking between interchangeable implementations (e.g. `Tts.default_provider`) → only the selected implementation's fields are required; enforce that via a `model_validator` on the parent, not a bare required field on each implementation.
- Never cite a `REQUIREMENTS.md` section number (`§3.3`, `§4.10`, "Step B2", ...) in a comment, docstring, or commit message body meant to explain the code itself. `REQUIREMENTS.md` is archived and deleted once the feature ships (see Development Process below), so a `§`-reference in source code becomes a dead pointer the moment that happens. Explain the *why* in the comment itself instead, in terms that stay true without the spec present.

## Development Process

Each feature is built incrementally against a `REQUIREMENTS.md` at the repo root, split into steps meant to be implemented, tested, and committed one at a time — see `docs/process/PROCESS.md` for the per-step loop and `docs/process/SELF_IMPROVE.md` for the required wrap-up. `REQUIREMENTS.md` and the per-feature self-improvement log are archived (e.g. to a GitHub issue) and removed once the feature ships; a new `REQUIREMENTS.md` is written per feature.
