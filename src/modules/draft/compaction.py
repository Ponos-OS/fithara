from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from src.modules.draft.context import estimate_tokens
from src.modules.draft.model import build_model
from src.modules.draft.types import ConversationTurn
from src.utils import get_settings


SUMMARY_TOKENS = 1_024
SUMMARY_PREFIX = "Summary of the earlier conversation:"
_PROMPT_PATH = Path(__file__).parent / "prompts" / "compact_v1.md"


@lru_cache(maxsize=1)
def load_compaction_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_compaction_agent(model: str | Model) -> Agent[None, str]:
    agent: Agent[None, str] = Agent(model, output_type=str)

    @agent.instructions
    def _instructions() -> str:
        return load_compaction_prompt()

    return agent


@lru_cache(maxsize=1)
def get_compaction_agent() -> Agent[None, str]:
    return build_compaction_agent(build_model(get_settings().llm))


def render_turn(turn: ConversationTurn) -> str:
    return f"{turn.role}: {turn.content}"


def split_history(
    turns: list[ConversationTurn], keep_recent_turns: int
) -> tuple[list[ConversationTurn], list[ConversationTurn]]:
    """Older turns to summarize, newest turns to keep verbatim."""

    split_at = max(len(turns) - keep_recent_turns, 0)

    return turns[:split_at], turns[split_at:]


def fit_to_budget(turns: list[ConversationTurn], max_tokens: int) -> list[ConversationTurn]:
    """Drops the oldest turns until the rest fits, so the summarizer itself never overflows."""

    kept: list[ConversationTurn] = []
    used = 0
    for turn in reversed(turns):
        used += estimate_tokens(render_turn(turn))
        if used > max_tokens:
            break
        kept.append(turn)

    return kept[::-1]


def clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    return text[: max_chars - 1] + "…"


async def compact_history(
    turns: list[ConversationTurn],
    *,
    keep_recent_turns: int,
    max_input_tokens: int,
    max_turn_chars: int,
    agent: Agent[None, str] | None = None,
) -> list[ConversationTurn]:
    """
    Replaces everything but the newest `keep_recent_turns` with one leading `assistant` summary
    turn. An earlier summary is just another older turn, so it is folded into the new one.
    """

    older, recent = split_history(turns, keep_recent_turns)
    if not older:
        return turns

    agent = agent or get_compaction_agent()
    result = await agent.run(
        "\n\n".join(render_turn(turn) for turn in fit_to_budget(older, max_input_tokens)),
        model_settings=ModelSettings(max_tokens=SUMMARY_TOKENS),
    )
    summary_turn = ConversationTurn(
        role="assistant",
        content=clip(f"{SUMMARY_PREFIX}\n{result.output.strip()}", max_turn_chars),
    )

    return [summary_turn, *recent]
