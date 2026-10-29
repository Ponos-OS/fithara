import logging
from types import SimpleNamespace

import llmcapa
import pytest

from src.utils.model_limits import HARDCODED_LIMITS, model_limits


def _capability(
    model_id: str, *, aliases: tuple[str, ...] = (), context_window: int = 0, max_output: int = 0
) -> SimpleNamespace:
    return SimpleNamespace(
        model_id=model_id,
        aliases=list(aliases),
        context_window=context_window,
        max_output_tokens=max_output,
    )


def _catalog(monkeypatch, *capabilities: SimpleNamespace) -> list[str | None]:
    providers: list[str | None] = []

    def list_models(provider: str | None = None) -> list[SimpleNamespace]:
        providers.append(provider)
        return list(capabilities)

    monkeypatch.setattr(llmcapa, "list_models", list_models)

    return providers


def test_a_model_is_found_by_its_id_or_alias_whatever_the_case(monkeypatch) -> None:
    _catalog(
        monkeypatch,
        _capability(
            "gpt-5.2", aliases=("gpt-5.2-2026-01-15",), context_window=400_000, max_output=128_000
        ),
    )

    by_alias = model_limits("GPT-5.2-2026-01-15", "openai")  # act

    assert (by_alias.context_window, by_alias.max_output_tokens) == (400_000, 128_000)


@pytest.mark.parametrize(
    ("provider", "searched"),
    [("openai", "openai"), ("anthropic", "anthropic"), ("ollama", None), (None, None)],
)
def test_the_catalog_is_searched_under_the_matching_provider_only(
    monkeypatch, provider: str | None, searched: str | None
) -> None:
    providers = _catalog(monkeypatch, _capability("m", context_window=1_000))

    model_limits("m", provider)  # act

    assert providers == [searched]


def test_a_limit_the_catalog_does_not_publish_is_none(monkeypatch) -> None:
    _catalog(monkeypatch, _capability("m", context_window=8_000, max_output=0))

    result = model_limits("m")

    assert (result.context_window, result.max_output_tokens) == (8_000, None)


def test_a_model_missing_from_the_catalog_falls_back_to_the_hardcoded_table(
    monkeypatch, caplog
) -> None:
    _catalog(monkeypatch)
    monkeypatch.setitem(HARDCODED_LIMITS, "my-model", (16_000, 4_000))
    caplog.set_level(logging.ERROR)

    result = model_limits("My-Model")

    assert (result.context_window, result.max_output_tokens) == (16_000, 4_000)
    assert "model_not_in_catalog" in caplog.text


def test_an_unknown_model_has_no_limits(monkeypatch) -> None:
    _catalog(monkeypatch)

    result = model_limits("mystery-model")

    assert (result.context_window, result.max_output_tokens) == (None, None)


def _broken_catalog(provider: str | None = None) -> list[SimpleNamespace]:
    raise RuntimeError("catalog unreadable")


def test_a_failing_catalog_lookup_falls_back_instead_of_raising(monkeypatch) -> None:
    monkeypatch.setattr(llmcapa, "list_models", _broken_catalog)

    result = model_limits("m")

    assert (result.context_window, result.max_output_tokens) == (None, None)
