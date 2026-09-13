"""
OpenTelemetry tracing + structured logging setup.

Mirrors the pattern in the sibling project `smart-novel-beatrice`: OTel
traces via OTLP/HTTP, and plain structured JSON logs to stdout correlated
to the active trace/span id (not pushed through the OTel Logs SDK — that's
a deliberate, narrower scope than "full OTel", matching what beatrice
actually ships).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import format_span_id, format_trace_id
from pydantic_ai import Agent

from src.utils.config import LoggingMode, Settings


_LOG_RECORD_STANDARD_FIELDS: frozenset[str] = frozenset(
    logging.LogRecord(
        name="",
        level=0,
        pathname="",
        lineno=0,
        msg="",
        args=None,
        exc_info=None,
    ).__dict__.keys()
    | {"message", "asctime"},
)
_configured: bool = False


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record on a single line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Correlate this log line with the active OTel trace/span, when there is
        # one, so a log can be linked back to the request that produced it.
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = format_trace_id(span_context.trace_id)
            payload["span_id"] = format_span_id(span_context.span_id)

        for key, value in record.__dict__.items():
            if key not in _LOG_RECORD_STANDARD_FIELDS:
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def _configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    root.setLevel(settings.logging.level.value.upper())

    # Remove pre-existing handlers: setup takes ownership of the root logger
    # when something else has already attached handlers first — pytest
    # capture, uvicorn defaults, a prior basicConfig call, an interactive reload.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler(stream=sys.stdout)

    if settings.logging.mode is LoggingMode.JSON:
        stream.setFormatter(JsonFormatter())
    else:
        stream.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S"
            )
        )

    root.addHandler(stream)

    # Uvicorn ships its own formatter — pipe its records through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True


def _configure_tracing(settings: Settings, version: str) -> None:
    resource = Resource.create({"service.name": settings.service_name, "service.version": version})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{settings.otel.exporter_otlp_endpoint}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # HTTPX must be instrumented before any AsyncClient is created — pydantic-ai
    # creates one internally the first time an Agent actually runs.
    HTTPXClientInstrumentor().instrument()

    # Turn on pydantic-ai's GenAI OTel instrumentation for every Agent in the
    # process. Emits gen_ai.* span attributes (provider, model, input/output
    # tokens) via the global TracerProvider we just installed. No-op when OTel
    # is disabled, since the global TracerProvider then stays the default NoOp
    # provider and these spans go nowhere.
    Agent.instrument_all(True)


def setup_observability(settings: Settings, version: str) -> None:
    """
    Wire up logging + (optionally) OpenTelemetry tracing.

    Idempotent: calling this more than once is a no-op.
    """

    global _configured
    if _configured:
        return

    _configure_logging(settings)

    if settings.otel.enabled:
        _configure_tracing(settings, version)

    _configured = True


def instrument_fastapi(app: FastAPI) -> None:
    """
    Attach the FastAPI OTel instrumentor to `app`.

    Kept separate from `setup_observability` because the FastAPI app doesn't
    exist yet at logging-init time. A no-op when OTel is disabled — the
    instrumentor still runs, but its spans get dropped by the default NoOp
    tracer provider.
    """

    FastAPIInstrumentor.instrument_app(app)
