from dataclasses import replace

import pytest
from fastapi import HTTPException

from src.modules.draft import ContextBudget, ConversationTurn, DraftRequest
from src.modules.draft.routes import enforce_conversation_limits
from src.utils import ErrorResponse


ROOMY = ContextBudget(
    prompt_tokens=100_000,
    response_tokens=1_000,
    compaction_input_tokens=100_000,
    keep_recent_turns=2,
)


def test_enforce_conversation_limits_passes_within_bounds() -> None:
    request = DraftRequest(
        conversation=[ConversationTurn(role="user", content="hi")],
        message="what does section 3 mean?",
    )

    result = enforce_conversation_limits(request, max_turns=5, max_message_chars=100, budget=ROOMY)

    assert result is False


@pytest.mark.parametrize(
    "request_",
    [
        DraftRequest(
            conversation=[ConversationTurn(role="user", content="hi") for _ in range(3)],
            message="hi",
        ),
        DraftRequest(message="x" * 101),
        DraftRequest(conversation=[ConversationTurn(role="user", content="x" * 101)], message="hi"),
    ],
    ids=["too many turns", "message too long", "turn content too long"],
)
def test_enforce_conversation_limits_rejects_oversized_input(request_: DraftRequest) -> None:
    with pytest.raises(HTTPException) as exc_info:
        enforce_conversation_limits(request_, max_turns=2, max_message_chars=100, budget=ROOMY)

    assert exc_info.value.status_code == 400
    error = ErrorResponse.model_validate(exc_info.value.detail)
    assert error.error.code == "INVALID_REQUEST"


def test_enforce_conversation_limits_asks_for_compaction_when_the_prompt_leaves_no_room() -> None:
    request = DraftRequest(
        conversation=[ConversationTurn(role="user", content="x" * 90) for _ in range(5)],
        message="hi",
    )
    tight = replace(ROOMY, prompt_tokens=100)

    result = enforce_conversation_limits(request, max_turns=5, max_message_chars=100, budget=tight)

    assert result is True
