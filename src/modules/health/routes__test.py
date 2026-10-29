from src.modules.health.routes import health
from src.utils import ModelLimits, Settings


def test_health_reports_the_model_and_its_limits_without_credentials(monkeypatch) -> None:
    monkeypatch.setenv("LLM__PROVIDER", "ollama")
    monkeypatch.setenv("LLM__MODEL", "llama3.2:3b")
    monkeypatch.setenv("LLM__API_KEY", "sk-super-secret-value")
    monkeypatch.setenv("LLM__BASE_URL", "http://ollama:11434/v1")
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    limits = ModelLimits("llama3.2:3b", context_window=131_072, max_output_tokens=None)

    result = health(settings, limits)  # act

    assert result.model_dump(by_alias=True) == {
        "status": "ok",
        "version": result.version,
        "llm": {"model": "llama3.2:3b", "contextWindow": 131_072, "maxOutputTokens": None},
    }
    assert "sk-super-secret-value" not in result.model_dump_json()
    assert "ollama:11434" not in result.model_dump_json()
