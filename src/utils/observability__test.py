from __future__ import annotations

import logging
import re
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.sdk.resources import Resource

from src.utils import observability
from src.utils.config import Llm, LogShipping, Otel, Settings


@pytest.fixture(autouse=True)
def _restore_root_handlers() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in original_handlers:
        root.addHandler(handler)


def test_log_export_attaches_an_otel_logging_handler_to_the_root_logger() -> None:
    settings = Settings(
        otel=Otel(enabled=True, exporter_otlp_endpoint="http://otel-collector:4318"),
        llm=Llm(
            provider="ollama",
            base_url="http://ollama:11434/v1",
            api_key="ollama",
            model="qwen2.5:3b",
        ),
    )

    observability._configure_log_export(
        settings, Resource.create({"service.name": "fithara"})
    )  # act

    assert any(isinstance(h, LoggingHandler) for h in logging.getLogger().handlers)


@pytest.mark.parametrize(
    ("log_shipping", "expected_handlers"),
    [("otlp", 1), ("stdout", 0)],
)
def test_tracing_pushes_logs_only_when_log_shipping_is_otlp(
    monkeypatch: pytest.MonkeyPatch, log_shipping: LogShipping, expected_handlers: int
) -> None:
    monkeypatch.setattr(observability.trace, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(
        observability,
        "HTTPXClientInstrumentor",
        lambda: type("_FakeInstrumentor", (), {"instrument": lambda self: None})(),
    )
    settings = Settings(
        otel=Otel(
            enabled=True,
            log_shipping=log_shipping,
            exporter_otlp_endpoint="http://otel-collector:4318",
        ),
        llm=Llm(
            provider="ollama",
            base_url="http://ollama:11434/v1",
            api_key="ollama",
            model="qwen2.5:3b",
        ),
    )

    observability._configure_tracing(settings, version="0.0.0")  # act

    handlers = [h for h in logging.getLogger().handlers if isinstance(h, LoggingHandler)]
    assert len(handlers) == expected_handlers


def _access_record(method: str, path: str, status_code: int) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("10.244.0.1:56632", method, path, "1.1", status_code),
        exc_info=None,
    )


@pytest.mark.parametrize(
    ("method", "path", "status_code", "is_kept"),
    [
        ("GET", "/health", 200, False),
        ("GET", "/health?probe=1", 200, False),
        ("GET", "/health", 503, True),
        ("GET", "/v1/licenses", 200, True),
        ("POST", "/health", 200, True),
    ],
)
def test_healthcheck_access_filter_drops_only_successful_probes(
    method: str, path: str, status_code: int, is_kept: bool
) -> None:
    record = _access_record(method, path, status_code)

    result = observability.HealthcheckAccessLogFilter().filter(record)

    assert result is is_kept


def test_setup_installs_the_healthcheck_filter_on_the_uvicorn_access_logger() -> None:
    observability._configured = False
    settings = Settings(
        otel=Otel(enabled=False),
        llm=Llm(
            provider="ollama",
            base_url="http://ollama:11434/v1",
            api_key="ollama",
            model="qwen2.5:3b",
        ),
    )

    observability.setup_observability(settings, version="0.0.0")  # act

    filters = logging.getLogger("uvicorn.access").filters
    assert any(isinstance(f, observability.HealthcheckAccessLogFilter) for f in filters)
    observability._configured = False


@pytest.mark.parametrize(
    ("url", "is_excluded"),
    [
        ("http://fithara:8000/health", True),
        ("http://fithara:8000/health?probe=1", True),
        ("http://fithara:8000/v1/licenses", False),
        ("http://fithara:8000/v1/health-tips", False),
    ],
)
def test_fastapi_instrumentation_excludes_only_the_healthcheck_url(
    monkeypatch: pytest.MonkeyPatch, url: str, is_excluded: bool
) -> None:
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        observability.FastAPIInstrumentor,
        "instrument_app",
        lambda app, **kwargs: captured.update(kwargs),
    )

    observability.instrument_fastapi(FastAPI())  # act

    assert bool(re.search(captured["excluded_urls"], url)) is is_excluded
