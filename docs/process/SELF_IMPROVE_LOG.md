# Self-improvement log

## History compaction and /health - 2026-10-29

- Added compaction of older conversation turns inside `POST /v1/draft` (the draft and the new message are never compacted), a `GET /health` with the model and its context window, and context settings. Left uncommitted for review; nothing was released.
- Every response now carries `conversation`, the history to send next time (summary turn as `assistant`, the recent turns, this turn's pair). On a fallback it is the incoming conversation unchanged. The LLM output type is `DraftReply`; `DraftResponse` adds `conversation`, so the model is never asked to produce it. Returned turns are clipped to `max_message_chars` so the next request is not rejected for them.
- Not verified against a live LLM: `make evals` needs a configured provider, and the new `compact_v1.md` prompt has no eval case. Summary quality and the token estimate (3 characters per token) are unchecked against a real model.
- `jscpd` fails `make lint_check` at 1.02%, so repeated fixture signatures and near-identical tests in new code tip it over; parametrize instead of copying.
- A new `src/modules/<name>/` package needs its own `importlinter` contract in `pyproject.toml`.

- The context window and output limit come from the `llmcapa` catalog through `src/utils/model_limits.py` (the same lookup nestral uses), not from settings; an unknown model fails at startup. A self-hosted Ollama may serve a smaller window than the catalog lists for its model, and nothing here can see that.
