from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from src.utils import CamelModel


class DraftSource(CamelModel):
    """Where a draft's text came from: an untouched canonical license, a fork of one, or fully custom."""

    type: Literal["canonical", "forked", "custom"]
    canonical_id: str | None = Field(
        default=None,
        description=(
            "The canonical license this draft is based on. Set when type is "
            "'canonical' or 'forked'; always null for 'custom'."
        ),
    )


class Draft(CamelModel):
    """The license text a user is currently working on."""

    title: str
    text: str = Field(description="The draft's license text, as Markdown.")
    source: DraftSource


class ConversationTurn(CamelModel):
    """One message in the conversation history, supplied by the client."""

    role: Literal["user", "assistant"]
    content: str


class Preferences(CamelModel):
    """Optional hints for the assistant. Never hard constraints."""

    category: str | None = Field(
        default=None,
        description="A canonical license category to prefer, e.g. 'creative_commons'.",
    )


class DraftRequest(CamelModel):
    """Request body for `POST /v1/draft`. Same shape on the first turn and every subsequent turn."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "conversation": [
                        {
                            "role": "user",
                            "content": (
                                "I want a license that lets people remix my novel but not sell it."
                            ),
                        },
                        {
                            "role": "assistant",
                            "content": "CC BY-NC 4.0 is likely a good fit...",
                        },
                    ],
                    "draft": {
                        "title": "Creative Commons Attribution-NonCommercial 4.0 International",
                        "text": "...",
                        "source": {"type": "canonical", "canonicalId": "CC-BY-NC-4.0"},
                    },
                    "message": "what does section 3 mean?",
                    "preferences": {"category": "creative_commons"},
                }
            ]
        }
    )

    conversation: list[ConversationTurn] = Field(
        default_factory=list,
        description="Full conversation history, client-supplied. May be empty on the first turn.",
    )
    draft: Draft | None = Field(
        default=None,
        description="Current draft state, client-supplied. May be null on the first turn.",
    )
    message: str = Field(description="The new user message. Required, non-empty.")
    preferences: Preferences | None = Field(
        default=None, description="Optional hints. Not hard constraints."
    )


class DraftResponse(CamelModel):
    """Response body for `POST /v1/draft`."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "assistantMessage": "Section 3 covers the attribution requirement...",
                    "draft": {
                        "title": "Creative Commons Attribution-NonCommercial 4.0 International",
                        "text": "...",
                        "source": {"type": "canonical", "canonicalId": "CC-BY-NC-4.0"},
                    },
                    "draftChanged": False,
                    "recommendations": ["CC-BY-NC-4.0", "CC-BY-NC-SA-4.0"],
                    "disclaimers": [
                        "This is not legal advice. Consult a qualified lawyer before "
                        "relying on this draft."
                    ],
                    "isReadyToFinalize": False,
                }
            ]
        }
    )

    assistant_message: str
    draft: Draft | None = Field(
        description="Current draft state after this turn. Null if no draft exists yet."
    )
    draft_changed: bool = Field(
        description="True iff the assistant created or modified the draft this turn."
    )
    recommendations: list[str] = Field(description="Canonical license IDs the assistant suggests.")
    disclaimers: list[str] = Field(description="Always non-empty. The client must render these.")
    is_ready_to_finalize: bool = Field(
        description="The assistant's opinion on readiness. The client decides whether to act on it."
    )
