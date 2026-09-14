from collections.abc import Callable

from fastapi import FastAPI
from httpx import AsyncClient
from tests.conftest import FIXTURE_ACTIVE_BODY

from src.modules.draft import DraftResponse, get_conversation_limits
from src.utils import Conversation, RateLimiter, get_rate_limiter


FALLBACK_ASSISTANT_MESSAGE = (
    "Sorry, I wasn't able to produce a reliable answer for that. "
    "Please try rephrasing your request."
)
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


async def test_draft_returns_schema_valid_response_for_a_recommendation(
    app: FastAPI, client: AsyncClient, stub_agent: Callable[[FastAPI, dict], None]
) -> None:
    stub_agent(app, CANONICAL_RESPONSE)

    response = await client.post(
        "/v1/draft",
        json={"message": "What license lets people remix my short story but not sell it?"},
    )  # act

    assert response.status_code == 200
    draft_response = DraftResponse.model_validate(response.json())
    assert draft_response.disclaimers


async def test_draft_multi_turn_conversation_stays_schema_valid(
    app: FastAPI, client: AsyncClient, stub_agent: Callable[[FastAPI, dict], None]
) -> None:
    stub_agent(app, CANONICAL_RESPONSE)
    first = await client.post(
        "/v1/draft",
        json={"message": "What license lets people remix my short story but not sell it?"},
    )
    first_body = first.json()

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
    DraftResponse.model_validate(second.json())


async def test_draft_falls_back_when_the_llm_call_fails(
    app: FastAPI, client: AsyncClient, failing_agent: Callable[[FastAPI], None]
) -> None:
    failing_agent(app)

    response = await client.post(
        "/v1/draft",
        json={"message": "What license lets people remix my short story but not sell it?"},
    )  # act

    assert response.status_code == 200
    body = response.json()
    DraftResponse.model_validate(body)
    assert body["assistantMessage"] == FALLBACK_ASSISTANT_MESSAGE
    assert body["draft"] is None


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
