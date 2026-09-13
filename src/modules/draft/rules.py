"""
The six draft-mutation rules — load-bearing invariants for `POST /v1/draft`:

1. Canonical match returns canonical verbatim — a draft claiming
   `source.type == "canonical"` must byte-equal the canonical body it
   claims to be.
2. Any modification forks the draft — a draft whose text no longer
   matches its canonical base must be labeled `source.type == "forked"`,
   with a title that doesn't claim to be the canonical license.
3. No base means custom — a draft with no canonical base
   (`source.type == "custom"`) must not carry a `canonical_id`.
4. Explanations do not mutate the draft — a turn reporting
   `draft_changed=False` must return the same draft as the previous turn.
5. The LLM never invents canonical text — subsumed by rules 1 and 3: the
   only way to claim "canonical" is byte-for-byte, and there's no fourth
   "invented canonical" category in the type system to fall into.
6. The LLM never writes to disk — architectural, not a per-turn check:
   nothing in this codebase persists a draft.

Rules 1-4 are checked below as pure functions: no network call, no LLM
call, no I/O. Each returns `True` when the draft complies and `False` on
violation.
"""

from __future__ import annotations

from src.modules.draft.types import Draft, DraftSource


def canonical_text_matches(draft: Draft, canonical_body: str) -> bool:
    """Rule 1: a draft claiming to be canonical must byte-equal the canonical body."""

    if draft.source.type != "canonical":
        return True

    return draft.text == canonical_body


def fork_is_labeled(draft: Draft, canonical_body: str, canonical_name: str) -> bool:
    """Rule 2: a draft whose text diverges from its canonical base must be labeled a fork, with a non-canonical-claiming title."""

    if draft.text == canonical_body:
        return True

    return draft.source.type == "forked" and draft.title != canonical_name


def custom_has_no_canonical_id(source: DraftSource) -> bool:
    """Rule 3: a custom draft (no canonical base) must not carry a canonical_id."""

    if source.type != "custom":
        return True

    return source.canonical_id is None


def draft_unchanged_when_not_changed(
    previous_draft: Draft | None, new_draft: Draft | None, draft_changed: bool
) -> bool:
    """Rule 4: a turn reporting draft_changed=False must return the same draft as the previous turn."""

    if draft_changed:
        return True

    return new_draft == previous_draft
