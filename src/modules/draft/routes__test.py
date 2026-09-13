import pytest
from fastapi import HTTPException

from src.modules.draft import ConversationTurn, DraftRequest
from src.modules.draft.routes import enforce_conversation_limits
from src.utils import ErrorResponse


def test_enforce_conversation_limits_passes_within_bounds() -> None:
    request = DraftRequest(
        conversation=[ConversationTurn(role="user", content="hi")],
        message="what does section 3 mean?",
    )

    enforce_conversation_limits(request, max_turns=5, max_message_chars=100)  # act


def test_enforce_conversation_limits_rejects_too_many_turns() -> None:
    request = DraftRequest(
        conversation=[ConversationTurn(role="user", content="hi") for _ in range(3)],
        message="hi",
    )

    with pytest.raises(HTTPException) as exc_info:
        enforce_conversation_limits(request, max_turns=2, max_message_chars=100)

    assert exc_info.value.status_code == 400
    error = ErrorResponse.model_validate(exc_info.value.detail)
    assert error.error.code == "INVALID_REQUEST"


def test_enforce_conversation_limits_rejects_message_too_long() -> None:
    request = DraftRequest(message="x" * 101)

    with pytest.raises(HTTPException) as exc_info:
        enforce_conversation_limits(request, max_turns=5, max_message_chars=100)

    assert exc_info.value.status_code == 400
    error = ErrorResponse.model_validate(exc_info.value.detail)
    assert error.error.code == "INVALID_REQUEST"


def test_enforce_conversation_limits_rejects_turn_content_too_long() -> None:
    request = DraftRequest(
        conversation=[ConversationTurn(role="user", content="x" * 101)],
        message="hi",
    )

    with pytest.raises(HTTPException) as exc_info:
        enforce_conversation_limits(request, max_turns=5, max_message_chars=100)

    assert exc_info.value.status_code == 400
    error = ErrorResponse.model_validate(exc_info.value.detail)
    assert error.error.code == "INVALID_REQUEST"
