from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.utils import CamelModel


class DraftSource(CamelModel):
    """Where a draft's text came from: an untouched canonical license, a fork of one, or fully custom."""

    type: Literal["canonical", "forked", "custom"]
    canonical_id: str | None = Field(
        default=None,
        examples=["CC-BY-NC-4.0"],
        description=(
            "The canonical license this draft is based on. Set when type is "
            "'canonical' or 'forked'; always null for 'custom'."
        ),
    )


class Draft(CamelModel):
    """The license text a user is currently working on."""

    title: str = Field(examples=["Creative Commons Attribution-NonCommercial 4.0 International"])
    text: str = Field(
        examples=["# Creative Commons Attribution-NonCommercial 4.0 International\n\n..."],
        description="The draft's license text, as Markdown.",
    )
    source: DraftSource


class ConversationTurn(CamelModel):
    """One message in the conversation history, supplied by the client."""

    role: Literal["user", "assistant"]
    content: str = Field(
        examples=["I want a license that lets people remix my novel but not sell it."]
    )


class Preferences(CamelModel):
    """Optional hints for the assistant. Never hard constraints."""

    category: str | None = Field(
        default=None,
        examples=["creative_commons"],
        description="A canonical license category to prefer, e.g. 'creative_commons'.",
    )


class DraftRequest(CamelModel):
    """A user's message plus everything the client currently knows: conversation so far and current draft."""

    conversation: list[ConversationTurn] = Field(
        default_factory=list,
        description="Full conversation history, client-supplied. May be empty on the first turn.",
    )
    draft: Draft | None = Field(
        default=None,
        description="Current draft state, client-supplied. May be null on the first turn.",
    )
    message: str = Field(
        examples=["what does section 3 mean?"],
        description="The new user message. Required, non-empty.",
    )
    preferences: Preferences | None = Field(
        default=None, description="Optional hints. Not hard constraints."
    )


class DraftResponse(CamelModel):
    """The assistant's reply: what it said, the (possibly updated) draft, and its recommendations."""

    assistant_message: str = Field(examples=["Section 3 covers the attribution requirement..."])
    draft: Draft | None = Field(
        description="Current draft state after this turn. Null if no draft exists yet."
    )
    draft_changed: bool = Field(
        description="True iff the assistant created or modified the draft this turn."
    )
    recommendations: list[str] = Field(
        examples=[["CC-BY-NC-4.0", "CC-BY-NC-SA-4.0"]],
        description="Canonical license IDs the assistant suggests.",
    )
    disclaimers: list[str] = Field(
        examples=[
            ["This is not legal advice. Consult a qualified lawyer before relying on this draft."]
        ],
        description="Always non-empty. The client must render these.",
    )
    is_ready_to_finalize: bool = Field(
        description="The assistant's opinion on readiness. The client decides whether to act on it."
    )
