"""Public API for src.modules.draft — the conversational drafting endpoint."""

from __future__ import annotations

from src.modules.draft.agent import build_agent, get_agent, run_draft_agent
from src.modules.draft.routes import router
from src.modules.draft.rules import (
    canonical_text_matches,
    custom_has_no_canonical_id,
    draft_unchanged_when_not_changed,
    fork_is_labeled,
)
from src.modules.draft.types import (
    ConversationTurn,
    Draft,
    DraftRequest,
    DraftResponse,
    DraftSource,
    Preferences,
)


__all__ = [
    "ConversationTurn",
    "Draft",
    "DraftRequest",
    "DraftResponse",
    "DraftSource",
    "Preferences",
    "build_agent",
    "canonical_text_matches",
    "custom_has_no_canonical_id",
    "draft_unchanged_when_not_changed",
    "fork_is_labeled",
    "get_agent",
    "router",
    "run_draft_agent",
]
