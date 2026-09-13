from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic_ai import Agent

from src.modules.draft.agent import get_agent, run_draft_agent
from src.modules.draft.types import DraftRequest, DraftResponse
from src.utils import ErrorResponse, enforce_rate_limit


router = APIRouter(tags=["draft"])


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
    request: DraftRequest, agent: Agent[None, DraftResponse] = Depends(get_agent)
) -> DraftResponse:
    return await run_draft_agent(request, agent=agent)
