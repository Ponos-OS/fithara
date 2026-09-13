from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic_ai import Agent

from src.modules.draft.agent import get_agent, run_draft_agent
from src.modules.draft.types import DraftRequest, DraftResponse
from src.registry import CanonicalLicense, get_registry
from src.utils import Conversation, ErrorResponse, api_error, enforce_rate_limit, get_settings


router = APIRouter(tags=["draft"])


def get_conversation_limits() -> Conversation:
    """FastAPI dependency: the process-wide `Conversation` limits. Overridable in tests via `app.dependency_overrides`."""

    return get_settings().conversation


def enforce_conversation_limits(
    request: DraftRequest, *, max_turns: int, max_message_chars: int
) -> None:
    """Reject a request whose conversation is too long or whose text exceeds `max_message_chars`."""

    if len(request.conversation) > max_turns:
        raise api_error("INVALID_REQUEST", f"conversation exceeds the maximum of {max_turns} turns")

    if len(request.message) > max_message_chars:
        raise api_error(
            "INVALID_REQUEST", f"message exceeds the maximum of {max_message_chars} characters"
        )

    for turn in request.conversation:
        if len(turn.content) > max_message_chars:
            raise api_error(
                "INVALID_REQUEST",
                f"a conversation turn exceeds the maximum of {max_message_chars} characters",
            )


@router.post(
    "/v1/draft",
    response_model=DraftResponse,
    dependencies=[Depends(enforce_rate_limit)],
    responses={
        400: {
            "model": ErrorResponse,
            "description": "The request failed validation, e.g. an empty `message`.",
        },
        429: {
            "model": ErrorResponse,
            "description": "Too many requests from this client within the configured rate-limit window.",
        },
    },
)
async def draft(
    request: DraftRequest,
    agent: Agent[None, DraftResponse] = Depends(get_agent),
    limits: Conversation = Depends(get_conversation_limits),
    registry: tuple[CanonicalLicense, ...] = Depends(get_registry),
) -> DraftResponse:
    enforce_conversation_limits(
        request, max_turns=limits.max_turns, max_message_chars=limits.max_message_chars
    )
    return await run_draft_agent(request, agent=agent, registry=registry)
