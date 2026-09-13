# Runbook: LLM Provider Outage

## What "outage" looks like from the outside

`POST /v1/draft` never returns a 5xx for an LLM failure — a failed call to the
provider (timeout, 401, 429, 5xx, network error) is caught and replaced with a
safe fallback response, always `200`:

```json
{
  "assistantMessage": "Sorry, I wasn't able to produce a reliable answer for that. Please try rephrasing your request.",
  "draft": null,
  "draftChanged": false,
  "recommendations": [],
  "disclaimers": ["This is not legal advice. Consult a qualified lawyer before relying on this draft."],
  "isReadyToFinalize": false
}
```

If users start reporting this exact message repeatedly (not as an occasional
one-off, which is expected retry-exhausted behavior for a single bad response),
the LLM provider is the first thing to check — not the service itself.

`GET /v1/licenses*` is unaffected by an LLM outage: the registry is loaded from
disk at startup, independent of the LLM provider.

## Confirming it's the provider

Every LLM call failure logs a structured warning:

```json
{"logger": "src.modules.draft.agent", "message": "draft_agent_llm_call_failed", "error_type": "ModelHTTPError", "status_code": 401, "model_name": "gpt-5.2"}
```

Grep stdout (or your log aggregator) for `draft_agent_llm_call_failed` and read
`error_type`/`status_code`. The message deliberately never includes the raw
provider error body or the API key: a provider's own error body can echo the
key back verbatim (confirmed against a real 401 from OpenAI), so only these
structured, provider-agnostic fields are logged.

If OTel tracing is enabled (`OTEL__ENABLED=true`), the same failure also shows
up as a `gen_ai.*` span (provider, model, error) via PydanticAI's built-in
instrumentation, correlated to the request's trace id.

## Interpreting `status_code`

| `status_code` | Likely cause | Action |
| --- | --- | --- |
| `401` / `403` | `LLM__API_KEY` is missing, wrong, or revoked | Rotate/fix the key in the deployment's env vars. |
| `429` | Provider-side rate limit hit | Wait, or raise the provider account's rate limit. Not related to this service's own `RATE_LIMIT__PER_MINUTE`. |
| `500`–`503` | Provider outage | Check the provider's public status page. Nothing to fix on our side; it will recover when they do. |
| `timeout` (no HTTP status; `error_type` won't be `ModelHTTPError`) | Provider slow or unreachable, or `LLM__TIMEOUT_MS` too low for the model in use | Check provider status; consider raising `LLM__TIMEOUT_MS` if this happens consistently on a normally-slow model. |

## What this runbook does not cover

- A canonical-integrity rejection (`draft_agent_canonical_integrity_check_failed`
  in the logs) is a *different* failure mode — the LLM replied, but the draft
  it returned didn't match the canonical text it claimed to be (a bug in the
  model's output, or a prompt-injection attempt). That's not a provider
  outage and needs no provider-side remediation; it's expected, safe
  behavior — the fallback response is what should reach the client either way.
- This is not a legal or content-quality escalation path. If a draft's
  *wording* looks wrong, that's a prompt/eval concern (`make evals`), not an
  outage.
