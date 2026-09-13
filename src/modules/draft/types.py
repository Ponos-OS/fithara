from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.utils import CamelModel


class DraftSource(CamelModel):
    type: Literal["canonical", "forked", "custom"]
    canonical_id: str | None = None


class Draft(CamelModel):
    title: str
    text: str
    source: DraftSource


class ConversationTurn(CamelModel):
    role: Literal["user", "assistant"]
    content: str


class Preferences(CamelModel):
    category: str | None = None


class DraftRequest(CamelModel):
    conversation: list[ConversationTurn] = Field(default_factory=list)
    draft: Draft | None = None
    message: str
    preferences: Preferences | None = None


class DraftResponse(CamelModel):
    assistant_message: str
    draft: Draft | None
    draft_changed: bool
    recommendations: list[str]
    disclaimers: list[str]
    is_ready_to_finalize: bool
