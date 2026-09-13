from pathlib import Path

import pytest
from pydantic import ValidationError

from src.utils import Settings


def _settings() -> Settings:
    """
    Construct `Settings` ignoring any real `.env` file in the repo root.

    Without `_env_file=None`, these tests would pass or fail depending on
    whether the developer has run `make init` locally (which creates a real
    `.env`) — `monkeypatch.delenv` only clears the process environment, not
    pydantic-settings' separate `.env`-file source.
    """

    return Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


def _set_required_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM__PROVIDER", "openai")
    monkeypatch.setenv("LLM__MODEL", "gpt-5.2")
    monkeypatch.setenv("LLM__API_KEY", "sk-test")


def test_settings_defaults_apply_when_absent(monkeypatch) -> None:
    _set_required_llm_env(monkeypatch)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("REGISTRY__PATH", raising=False)

    settings = _settings()  # act

    assert settings.port == 8000
    assert settings.registry.path == Path("./src/licenses")
    assert settings.llm.timeout_ms == 30_000
    assert settings.rate_limit.per_minute == 60
    assert settings.conversation.max_turns == 50
    assert settings.conversation.max_message_chars == 4_000


def test_settings_reads_nested_registry_path_env_var(monkeypatch) -> None:
    _set_required_llm_env(monkeypatch)
    monkeypatch.setenv("REGISTRY__PATH", "/tmp/licenses-fixture")

    settings = _settings()  # act

    assert settings.registry.path == Path("/tmp/licenses-fixture")


def test_settings_reads_flat_port_env_var(monkeypatch) -> None:
    _set_required_llm_env(monkeypatch)
    monkeypatch.setenv("PORT", "9000")

    settings = _settings()  # act

    assert settings.port == 9000


def test_settings_raises_when_llm_provider_missing(monkeypatch) -> None:
    monkeypatch.delenv("LLM__PROVIDER", raising=False)
    monkeypatch.setenv("LLM__MODEL", "gpt-5.2")
    monkeypatch.setenv("LLM__API_KEY", "sk-test")

    with pytest.raises(ValidationError):
        _settings()


def test_settings_reads_llm_nested_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("LLM__PROVIDER", "openai")
    monkeypatch.setenv("LLM__MODEL", "gpt-5.2")
    monkeypatch.setenv("LLM__API_KEY", "sk-test")
    monkeypatch.setenv("LLM__TIMEOUT_MS", "5000")

    settings = _settings()  # act

    assert settings.llm.provider == "openai"
    assert settings.llm.model == "gpt-5.2"
    assert settings.llm.api_key == "sk-test"
    assert settings.llm.timeout_ms == 5000


def test_settings_reads_rate_limit_nested_env_var(monkeypatch) -> None:
    _set_required_llm_env(monkeypatch)
    monkeypatch.setenv("RATE_LIMIT__PER_MINUTE", "5")

    settings = _settings()  # act

    assert settings.rate_limit.per_minute == 5


def test_settings_reads_conversation_nested_env_vars(monkeypatch) -> None:
    _set_required_llm_env(monkeypatch)
    monkeypatch.setenv("CONVERSATION__MAX_TURNS", "10")
    monkeypatch.setenv("CONVERSATION__MAX_MESSAGE_CHARS", "500")

    settings = _settings()  # act

    assert settings.conversation.max_turns == 10
    assert settings.conversation.max_message_chars == 500
