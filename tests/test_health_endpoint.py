from fastapi import FastAPI
from httpx import AsyncClient

from src.utils import ModelLimits, Settings, get_model_limits, get_settings


async def test_health_reports_status_version_and_model_limits(
    app: FastAPI, client: AsyncClient
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        llm={"provider": "openai", "model": "gpt-5.2", "api_key": "sk-test"},
    )
    app.dependency_overrides[get_model_limits] = lambda: ModelLimits(
        "gpt-5.2", context_window=400_000, max_output_tokens=128_000
    )

    response = await client.get("/health")  # act

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm"] == {"model": "gpt-5.2", "contextWindow": 400_000, "maxOutputTokens": 128_000}
