import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.modules.draft import build_agent, get_agent
from src.utils import RateLimiter, get_rate_limiter


def _stub_agent(app: FastAPI, payload: dict) -> None:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        tool_name = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(tool_name, payload)])

    app.dependency_overrides[get_agent] = lambda: build_agent(FunctionModel(respond))


CANONICAL_RESPONSE = {
    "assistantMessage": "CC BY-NC 4.0 fits your needs, here it is verbatim.",
    "draft": {
        "title": "Creative Commons Attribution-NonCommercial 4.0 International",
        "text": "verbatim canonical body",
        "source": {"type": "canonical", "canonicalId": "CC-BY-NC-4.0"},
    },
    "draftChanged": True,
    "recommendations": ["CC-BY-NC-4.0"],
    "disclaimers": ["This is not legal advice."],
    "isReadyToFinalize": False,
}

FORKED_RESPONSE = {
    "assistantMessage": "I've adjusted the license; this is now a custom fork.",
    "draft": {
        "title": "Custom license (derived from CC BY-NC 4.0)",
        "text": "verbatim body, with the added indie-publisher carve-out",
        "source": {"type": "forked", "canonicalId": "CC-BY-NC-4.0"},
    },
    "draftChanged": True,
    "recommendations": [],
    "disclaimers": ["This is not legal advice.", "This is a modified license."],
    "isReadyToFinalize": False,
}

CUSTOM_RESPONSE = {
    "assistantMessage": "No canonical license fits, here's a custom draft.",
    "draft": {
        "title": "Custom Attribution License",
        "text": "a fully custom license body",
        "source": {"type": "custom", "canonicalId": None},
    },
    "draftChanged": True,
    "recommendations": [],
    "disclaimers": ["This is not legal advice."],
    "isReadyToFinalize": False,
}

EXPLANATION_RESPONSE = {
    "assistantMessage": "Section 3 covers the attribution requirement.",
    "draft": {
        "title": "Creative Commons Attribution-NonCommercial 4.0 International",
        "text": "verbatim canonical body",
        "source": {"type": "canonical", "canonicalId": "CC-BY-NC-4.0"},
    },
    "draftChanged": False,
    "recommendations": [],
    "disclaimers": ["This is not legal advice."],
    "isReadyToFinalize": False,
}


@pytest.mark.parametrize(
    "payload",
    [CANONICAL_RESPONSE, FORKED_RESPONSE, CUSTOM_RESPONSE],
)
async def test_draft_returns_schema_valid_response_per_source_type(
    app: FastAPI, client: AsyncClient, payload: dict
) -> None:
    _stub_agent(app, payload)

    response = await client.post("/v1/draft", json={"message": "doesn't matter, mocked"})  # act

    assert response.status_code == 200
    assert response.json() == payload


async def test_draft_explanation_turn_reports_draft_changed_false(
    app: FastAPI, client: AsyncClient
) -> None:
    _stub_agent(app, EXPLANATION_RESPONSE)

    response = await client.post("/v1/draft", json={"message": "what does section 3 mean?"})  # act

    assert response.status_code == 200
    assert response.json()["draftChanged"] is False


async def test_draft_returns_400_for_empty_message(app: FastAPI, client: AsyncClient) -> None:
    _stub_agent(app, CANONICAL_RESPONSE)

    response = await client.post("/v1/draft", json={"message": ""})  # act

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


async def test_draft_returns_400_for_missing_message(app: FastAPI, client: AsyncClient) -> None:
    _stub_agent(app, CANONICAL_RESPONSE)

    response = await client.post("/v1/draft", json={})  # act

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


async def test_draft_returns_429_once_rate_limit_exceeded(
    app: FastAPI, client: AsyncClient
) -> None:
    _stub_agent(app, CANONICAL_RESPONSE)
    strict_limiter = RateLimiter(per_minute=1)
    app.dependency_overrides[get_rate_limiter] = lambda: strict_limiter
    await client.post("/v1/draft", json={"message": "first request"})

    response = await client.post("/v1/draft", json={"message": "second request"})  # act

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


async def test_draft_end_to_end_flow_recommend_explain_fork(
    app: FastAPI, client: AsyncClient
) -> None:
    _stub_agent(app, CANONICAL_RESPONSE)
    recommend = await client.post(
        "/v1/draft", json={"message": "what license lets people remix but not sell?"}
    )

    assert recommend.status_code == 200
    assert recommend.json()["draft"]["source"]["type"] == "canonical"

    _stub_agent(app, EXPLANATION_RESPONSE)
    explain = await client.post("/v1/draft", json={"message": "what does section 3 mean?"})

    assert explain.status_code == 200
    assert explain.json()["draftChanged"] is False

    _stub_agent(app, FORKED_RESPONSE)
    fork = await client.post(
        "/v1/draft", json={"message": "allow small indie authors to sell"}
    )  # act

    assert fork.status_code == 200
    assert fork.json()["draft"]["source"]["type"] == "forked"
    assert (
        fork.json()["draft"]["title"]
        != "Creative Commons Attribution-NonCommercial 4.0 International"
    )
