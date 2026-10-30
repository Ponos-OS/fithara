<h1><img src="./favicon.svg" width="40" height="40" alt="Fithara logo" /> Fithara</h1>

A stateless, LLM-assisted REST service that helps users pick and draft a content license for a written work, from a curated registry of canonical licenses (CC-BY, CC-BY-SA, CC-BY-NC, CC-BY-NC-SA).

The API Docs lives here: https://ponos-os.github.io/fithara/

## Docker Image

https://hub.docker.com/r/9109679196/fithara

```shell
docker run --rm -p 8000:8000 \
  -e LLM__PROVIDER=openai \
  -e LLM__MODEL=gpt-5.2 \
  -e LLM__API_KEY=sk-... \
  9109679196/fithara:latest
```

The API is then served on http://localhost:8000. Pin a release tag instead of `latest` for anything beyond a trial.

### Environment Variables

| Variable                          | Default                 | Description                                                                             |
| --------------------------------- | ----------------------- | --------------------------------------------------------------------------------------- |
| `LLM__PROVIDER`                   | required                | PydanticAI provider, e.g. `openai`, `anthropic`, `ollama`.                              |
| `LLM__MODEL`                      | required                | Model name, e.g. `gpt-5.2`.                                                             |
| `LLM__API_KEY`                    | required                | Provider API key.                                                                       |
| `LLM__BASE_URL`                   | provider default        | Override the provider API base URL, e.g. a self-hosted Ollama server.                   |
| `LLM__TIMEOUT_MS`                 | `30000`                 | LLM request timeout in milliseconds (minimum `1000`).                                   |
| `RATE_LIMIT__PER_MINUTE`          | `60`                    | Requests per minute per key/IP.                                                         |
| `CONVERSATION__MAX_TURNS`         | `50`                    | Maximum entries allowed in `conversation`.                                              |
| `CONVERSATION__MAX_MESSAGE_CHARS` | `4000`                  | Maximum characters in `message` or any turn's `content`.                                |
| `CONVERSATION__KEEP_RECENT_TURNS` | `4`                     | Newest turns kept verbatim when older ones are summarized.                              |
| `REGISTRY__PATH`                  | `./src/licenses`        | Directory of canonical license Markdown files.                                          |
| `LOGGING__MODE`                   | `JSON`                  | `JSON` or `PLAIN_TEXT`.                                                                 |
| `LOGGING__LEVEL`                  | `info`                  | `debug`, `info`, `warning`, `error` or `critical`.                                      |
| `OTEL__ENABLED`                   | `false`                 | Export traces to an OTLP collector.                                                     |
| `OTEL__EXPORTER_OTLP_ENDPOINT`    | `http://localhost:4318` | OTLP/HTTP collector base URL.                                                           |
| `OTEL__LOG_SHIPPING`              | `otlp`                  | `otlp` pushes logs to the collector, `stdout` leaves them to a shipper that tails them. |
| `OTEL__TRACES_SAMPLER`            | `parentbased_always_on` | OpenTelemetry sampler.                                                                  |
| `SERVICE_NAME`                    | `fithara`               | Service identifier reported to OTel.                                                    |
