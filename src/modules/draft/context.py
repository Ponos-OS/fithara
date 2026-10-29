from __future__ import annotations

import math
from dataclasses import dataclass

from src.registry import CanonicalLicense
from src.utils import Conversation, ModelLimits


# No tokenizer ships with the service, and an exact count would differ per model anyway.
# Fewer characters per token than English averages errs on the side of compacting early.
_CHARS_PER_TOKEN = 3
# A response holds the whole draft again, and a fork may grow past the license it started from.
RESPONSE_SLACK_TOKENS = 2_048


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / _CHARS_PER_TOKEN)


@dataclass(frozen=True)
class ContextBudget:
    """What the model's context window leaves for each part of one `POST /v1/draft` call."""

    prompt_tokens: int
    response_tokens: int
    compaction_input_tokens: int
    keep_recent_turns: int
    max_turns: int = 50
    max_turn_chars: int = 4_000


def build_context_budget(
    limits: ModelLimits,
    conversation: Conversation,
    *,
    instructions: str,
    compaction_instructions: str,
    summary_tokens: int,
    registry: tuple[CanonicalLicense, ...],
) -> ContextBudget:
    """
    A response must be able to return the longest canonical license whole, so that is what is
    reserved for it (and capped at). The prompt gets the window minus that, the system prompt and
    one canonical license: the agent can fetch a license body with a tool, and that lands in the
    context too.
    """

    if limits.context_window is None:
        raise ValueError(
            f"the model {limits.model!r} is not in the capability catalog; add its context window "
            "and maximum output tokens to HARDCODED_LIMITS in src/utils/model_limits.py"
        )

    largest_license_tokens = max(
        (estimate_tokens(license_.body_markdown) for license_ in registry), default=0
    )
    response_tokens = largest_license_tokens + RESPONSE_SLACK_TOKENS
    if limits.max_output_tokens is not None and limits.max_output_tokens < response_tokens:
        raise ValueError(
            f"the model {limits.model!r} can answer with at most {limits.max_output_tokens} tokens, "
            f"fewer than the {response_tokens} needed to return the longest canonical license"
        )

    prompt_tokens = (
        limits.context_window
        - response_tokens
        - estimate_tokens(instructions)
        - largest_license_tokens
    )
    if prompt_tokens <= 0:
        raise ValueError(
            f"the context window of {limits.model!r} ({limits.context_window} tokens) is too small "
            "for the system prompt, the longest canonical license and its response"
        )

    return ContextBudget(
        prompt_tokens=prompt_tokens,
        response_tokens=response_tokens,
        compaction_input_tokens=limits.context_window
        - summary_tokens
        - estimate_tokens(compaction_instructions),
        keep_recent_turns=conversation.keep_recent_turns,
        max_turns=conversation.max_turns,
        max_turn_chars=conversation.max_message_chars,
    )
