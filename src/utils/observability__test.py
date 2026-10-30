from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
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
