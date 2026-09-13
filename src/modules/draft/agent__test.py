import pytest
from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.modules.draft import DraftRequest, build_agent, run_draft_agent


def _model_returning(payload: dict) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        tool_name = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(tool_name, payload)])

    return FunctionModel(respond)


RECOMMENDATION_ONLY_RESPONSE = {
    "assistantMessage": "CC BY-NC 4.0 or CC BY-NC-SA 4.0 would both fit what you're describing.",
    "draft": None,
    "draftChanged": False,
    "recommendations": ["CC-BY-NC-4.0", "CC-BY-NC-SA-4.0"],
    "disclaimers": ["This is not legal advice."],
    "isReadyToFinalize": False,
}

CANONICAL_MATCH_RESPONSE = {
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

FORK_RESPONSE = {
    "assistantMessage": (
        "I've adjusted the license so small publishers can sell it; this is now a "
        "custom fork, not CC BY-NC 4.0 itself."
    ),
    "draft": {
        "title": "Custom license (derived from CC BY-NC 4.0)",
        "text": "verbatim body, with the added indie-publisher carve-out",
        "source": {"type": "forked", "canonicalId": "CC-BY-NC-4.0"},
    },
    "draftChanged": True,
    "recommendations": [],
    "disclaimers": [
        "This is not legal advice.",
        "This is a modified license, no longer equivalent to CC BY-NC 4.0.",
    ],
    "isReadyToFinalize": False,
}

PURE_EXPLANATION_RESPONSE = {
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

REFUSAL_RESPONSE = {
    "assistantMessage": (
        "I can't relabel a modified license as CC BY 4.0 — that would misrepresent it. "
        "I can create a custom fork instead if you'd like."
    ),
    "draft": None,
    "draftChanged": False,
    "recommendations": [],
    "disclaimers": ["This is not legal advice."],
    "isReadyToFinalize": False,
}


@pytest.mark.parametrize(
    "payload",
    [
        RECOMMENDATION_ONLY_RESPONSE,
        CANONICAL_MATCH_RESPONSE,
        FORK_RESPONSE,
        PURE_EXPLANATION_RESPONSE,
        REFUSAL_RESPONSE,
    ],
)
async def test_run_draft_agent_produces_schema_valid_response_for_golden_scenario(
    payload: dict,
) -> None:
    request = DraftRequest(message="doesn't matter, the model is mocked")
    agent = build_agent("test")

    with agent.override(model=_model_returning(payload)):
        response = await run_draft_agent(request, agent=agent)  # act

    assert response.model_dump(by_alias=True) == payload


async def test_run_draft_agent_falls_back_after_repeated_invalid_output() -> None:
    def always_invalid(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        tool_name = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(tool_name, {"assistantMessage": 123})])

    request = DraftRequest(message="doesn't matter, the model is mocked")
    agent = build_agent("test")

    with agent.override(model=FunctionModel(always_invalid)):
        response = await run_draft_agent(request, agent=agent)  # act

    assert response.draft_changed is False
    assert response.draft is None
    assert response.disclaimers
