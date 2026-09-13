import pytest
from pydantic import ValidationError

from src.modules.draft import (
    ConversationTurn,
    Draft,
    DraftRequest,
    DraftResponse,
    DraftSource,
    Preferences,
)


def test_draft_source_round_trips_camel_case_json() -> None:
    source = DraftSource(type="canonical", canonical_id="CC-BY-4.0")

    dumped = source.model_dump(by_alias=True)  # act

    assert dumped == {"type": "canonical", "canonicalId": "CC-BY-4.0"}
    assert DraftSource.model_validate(dumped) == source


def test_draft_round_trips() -> None:
    draft = Draft(title="My License", text="license body", source=DraftSource(type="custom"))

    dumped = draft.model_dump(by_alias=True)  # act

    assert Draft.model_validate(dumped) == draft


def test_conversation_turn_round_trips() -> None:
    turn = ConversationTurn(role="user", content="what license should I use?")

    dumped = turn.model_dump(by_alias=True)  # act

    assert ConversationTurn.model_validate(dumped) == turn


def test_preferences_round_trips_with_null_category() -> None:
    preferences = Preferences()

    dumped = preferences.model_dump(by_alias=True)  # act

    assert dumped == {"category": None}
    assert Preferences.model_validate(dumped) == preferences


def test_draft_request_round_trips_with_null_draft_and_preferences() -> None:
    request = DraftRequest(message="what does section 3 mean?")

    dumped = request.model_dump(by_alias=True)  # act

    assert dumped["draft"] is None
    assert dumped["preferences"] is None
    assert DraftRequest.model_validate(dumped) == request


def test_draft_request_strips_message_whitespace() -> None:
    request = DraftRequest(message="  what does section 3 mean?  ")  # act

    assert request.message == "what does section 3 mean?"


def test_draft_request_rejects_whitespace_only_message() -> None:
    with pytest.raises(ValidationError):
        DraftRequest(message="   ")


def test_draft_request_round_trips_with_conversation_and_draft() -> None:
    request = DraftRequest(
        conversation=[ConversationTurn(role="user", content="hi")],
        draft=Draft(title="t", text="body", source=DraftSource(type="canonical", canonical_id="X")),
        message="what does section 3 mean?",
        preferences=Preferences(category="creative_commons"),
    )

    dumped = request.model_dump(by_alias=True)  # act

    assert DraftRequest.model_validate(dumped) == request


def test_draft_response_round_trips_with_null_draft() -> None:
    response = DraftResponse(
        assistant_message="Here's what I recommend.",
        draft=None,
        draft_changed=False,
        recommendations=["CC-BY-4.0"],
        disclaimers=["This is not legal advice."],
        is_ready_to_finalize=False,
    )

    dumped = response.model_dump(by_alias=True)  # act

    assert dumped["draftChanged"] is False
    assert dumped["isReadyToFinalize"] is False
    assert dumped["draft"] is None
    assert DraftResponse.model_validate(dumped) == response
