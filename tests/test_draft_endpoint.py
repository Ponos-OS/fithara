from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from tests.conftest import FALLBACK_ASSISTANT_MESSAGE, FIXTURE_ACTIVE_BODY, build_test_app

from src.modules.draft import DraftResponse, get_conversation_limits
from src.utils import Conversation, RateLimiter, get_rate_limiter


@pytest.fixture
def app(fixture_registry_dir: Path, ollama_env: None) -> FastAPI:
    return build_test_app(fixture_registry_dir)


CANONICAL_RESPONSE = {
    "assistantMessage": "Fixture Active License fits your needs, here it is verbatim.",
    "draft": {
        "title": "Fixture Active License",
        "text": FIXTURE_ACTIVE_BODY,
        "source": {"type": "canonical", "canonicalId": "FIXTURE-ACTIVE"},
    },
    "draftChanged": True,
    "recommendations": ["FIXTURE-ACTIVE"],
    "disclaimers": ["This is not legal advice."],
    "isReadyToFinalize": False,
}


async def test_draft_returns_schema_valid_response_for_a_real_recommendation(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/v1/draft",
        json={"message": "What license lets people remix my short story but not sell it?"},
    )  # act

    assert response.status_code == 200
    body = response.json()
    draft_response = DraftResponse.model_validate(body)
    assert draft_response.assistant_message != FALLBACK_ASSISTANT_MESSAGE
    assert draft_response.disclaimers


async def test_draft_multi_turn_conversation_stays_schema_valid(client: AsyncClient) -> None:
    first = await client.post(
        "/v1/draft",
        json={"message": "What license lets people remix my short story but not sell it?"},
    )

    assert first.status_code == 200
    first_body = first.json()
    assert first_body["assistantMessage"] != FALLBACK_ASSISTANT_MESSAGE

    second = await client.post(
        "/v1/draft",
        json={
            "message": "Can you explain the current draft to me?",
            "draft": first_body["draft"],
            "conversation": [
                {
                    "role": "user",
                    "content": "What license lets people remix my short story but not sell it?",
                },
                {"role": "assistant", "content": first_body["assistantMessage"]},
            ],
        },
    )  # act

    assert second.status_code == 200
    second_body = second.json()
    DraftResponse.model_validate(second_body)
    assert second_body["assistantMessage"] != FALLBACK_ASSISTANT_MESSAGE


async def test_draft_returns_400_for_empty_message(
    app: FastAPI, client: AsyncClient, stub_agent: Callable[[FastAPI, dict], None]
) -> None:
    stub_agent(app, CANONICAL_RESPONSE)

    response = await client.post("/v1/draft", json={"message": ""})  # act

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


async def test_draft_returns_400_for_missing_message(
    app: FastAPI, client: AsyncClient, stub_agent: Callable[[FastAPI, dict], None]
) -> None:
    stub_agent(app, CANONICAL_RESPONSE)

    response = await client.post("/v1/draft", json={})  # act

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


async def test_draft_returns_400_for_message_over_the_length_limit(
    app: FastAPI, client: AsyncClient, stub_agent: Callable[[FastAPI, dict], None]
) -> None:
    stub_agent(app, CANONICAL_RESPONSE)
    app.dependency_overrides[get_conversation_limits] = lambda: Conversation(
        max_turns=50, max_message_chars=10
    )

    response = await client.post("/v1/draft", json={"message": "x" * 11})  # act

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


async def test_draft_returns_429_once_rate_limit_exceeded(
    app: FastAPI, client: AsyncClient, stub_agent: Callable[[FastAPI, dict], None]
) -> None:
    stub_agent(app, CANONICAL_RESPONSE)
    strict_limiter = RateLimiter(per_minute=1)
    app.dependency_overrides[get_rate_limiter] = lambda: strict_limiter
    await client.post("/v1/draft", json={"message": "first request"})

    response = await client.post("/v1/draft", json={"message": "second request"})  # act

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
