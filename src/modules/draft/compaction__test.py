from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.modules.draft.compaction import (
    SUMMARY_PREFIX,
    SUMMARY_TOKENS,
    build_compaction_agent,
    compact_history,
    fit_to_budget,
    split_history,
)
from src.modules.draft.types import ConversationTurn


def _turns(count: int) -> list[ConversationTurn]:
    return [
        ConversationTurn(role="user" if index % 2 == 0 else "assistant", content=f"turn {index}")
        for index in range(count)
    ]


def _summarizer(summary: str) -> tuple[FunctionModel, list[tuple[str, int | None]]]:
    calls: list[tuple[str, int | None]] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = str(messages[-1].parts[-1].content)  # pyright: ignore[reportAttributeAccessIssue]
        calls.append((prompt, (info.model_settings or {}).get("max_tokens")))
        return ModelResponse(parts=[TextPart(summary)])

    return FunctionModel(respond), calls


def test_split_history_keeps_the_newest_turns() -> None:
    turns = _turns(6)

    result = split_history(turns, 2)

    assert result == (turns[:4], turns[4:])


def test_split_history_with_fewer_turns_than_kept_has_nothing_to_summarize() -> None:
    turns = _turns(2)

    result = split_history(turns, 4)

    assert result == ([], turns)


def test_split_history_with_zero_kept_summarizes_everything() -> None:
    turns = _turns(3)

    result = split_history(turns, 0)

    assert result == (turns, [])


def test_fit_to_budget_drops_the_oldest_turns_first() -> None:
    turns = [
        ConversationTurn(role="user", content="a" * 30),
        ConversationTurn(role="assistant", content="b" * 30),
        ConversationTurn(role="user", content="c" * 30),
    ]

    result = fit_to_budget(turns, 30)

    assert result == turns[1:]


async def test_compact_history_replaces_the_older_turns_with_one_assistant_summary() -> None:
    model, calls = _summarizer("  The author wants remixing allowed but no resale.  ")
    agent = build_compaction_agent(model)
    turns = _turns(6)

    result = await compact_history(
        turns, keep_recent_turns=2, max_input_tokens=10_000, max_turn_chars=4_000, agent=agent
    )  # act

    assert result == [
        ConversationTurn(
            role="assistant",
            content=f"{SUMMARY_PREFIX}\nThe author wants remixing allowed but no resale.",
        ),
        *turns[4:],
    ]
    prompt, max_tokens = calls[0]
    assert prompt == "\n\n".join(f"{t.role}: {t.content}" for t in turns[:4])
    assert max_tokens == SUMMARY_TOKENS


async def test_compact_history_folds_an_earlier_summary_into_the_new_one() -> None:
    model, calls = _summarizer("Merged summary.")
    agent = build_compaction_agent(model)
    earlier = ConversationTurn(
        role="assistant", content=f"{SUMMARY_PREFIX}\nThe author is a novelist."
    )
    turns = [earlier, *_turns(5)]

    result = await compact_history(
        turns, keep_recent_turns=2, max_input_tokens=10_000, max_turn_chars=4_000, agent=agent
    )  # act

    assert calls[0][0].startswith(f"assistant: {SUMMARY_PREFIX}\nThe author is a novelist.")
    assert [turn.content for turn in result[1:]] == ["turn 3", "turn 4"]
    assert result[0].content == f"{SUMMARY_PREFIX}\nMerged summary."


async def test_compact_history_keeps_the_summary_within_the_turn_length_limit() -> None:
    model, _ = _summarizer("x" * 500)
    agent = build_compaction_agent(model)

    result = await compact_history(
        _turns(6), keep_recent_turns=2, max_input_tokens=10_000, max_turn_chars=100, agent=agent
    )  # act

    assert len(result[0].content) == 100
    assert result[0].content.endswith("…")


async def test_compact_history_does_not_call_the_model_when_there_is_nothing_older() -> None:
    model, calls = _summarizer("unused")
    agent = build_compaction_agent(model)
    turns = _turns(3)

    result = await compact_history(
        turns, keep_recent_turns=4, max_input_tokens=10_000, max_turn_chars=4_000, agent=agent
    )  # act

    assert result == turns
    assert calls == []
