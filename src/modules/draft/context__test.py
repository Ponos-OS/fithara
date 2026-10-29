import pytest

from src.modules.draft.context import RESPONSE_SLACK_TOKENS, build_context_budget, estimate_tokens
from src.registry import CanonicalLicense
from src.utils import Conversation, ModelLimits


def _license(body: str) -> CanonicalLicense:
    return CanonicalLicense(
        id="CC-BY-4.0",
        name="Creative Commons Attribution 4.0 International",
        short_name="CC BY 4.0",
        version="4.0",
        category="creative_commons",
        official_url="https://example.com/CC-BY-4.0",
        summary="A fixture license.",
        permissions=["share"],
        limitations=[],
        conditions=["attribution"],
        active=True,
        order=10,
        body_markdown=body,
    )


@pytest.mark.parametrize(("text", "expected"), [("", 0), ("abc", 1), ("abcd", 2), ("a" * 300, 100)])
def test_estimate_tokens_rounds_up(text: str, expected: int) -> None:
    result = estimate_tokens(text)

    assert result == expected


def _build(limits: ModelLimits, *, license_chars: int = 3_000, summary_tokens: int = 1_000):
    return build_context_budget(
        limits,
        Conversation(keep_recent_turns=3),
        instructions="x" * 300,
        compaction_instructions="y" * 150,
        summary_tokens=summary_tokens,
        registry=(_license("a" * 600), _license("b" * license_chars)),
    )


def test_build_context_budget_reserves_a_whole_license_for_the_response() -> None:
    limits = ModelLimits("gpt-5.2", context_window=50_000, max_output_tokens=128_000)

    result = _build(limits)

    assert result.response_tokens == 1_000 + RESPONSE_SLACK_TOKENS
    assert result.prompt_tokens == 50_000 - (1_000 + RESPONSE_SLACK_TOKENS) - 100 - 1_000
    assert result.compaction_input_tokens == 50_000 - 1_000 - 50
    assert result.keep_recent_turns == 3
    assert result.max_turns == 50
    assert result.max_turn_chars == 4_000


def test_build_context_budget_accepts_a_model_with_no_published_output_limit() -> None:
    limits = ModelLimits("local-model", context_window=50_000, max_output_tokens=None)

    result = _build(limits)

    assert result.response_tokens == 1_000 + RESPONSE_SLACK_TOKENS


def test_build_context_budget_rejects_a_model_the_catalog_does_not_know() -> None:
    limits = ModelLimits("mystery-model")

    with pytest.raises(ValueError, match="not in the capability catalog"):
        _build(limits)


def test_build_context_budget_rejects_a_model_that_cannot_answer_with_a_whole_license() -> None:
    limits = ModelLimits("small-output", context_window=50_000, max_output_tokens=2_000)

    with pytest.raises(ValueError, match="can answer with at most 2000 tokens"):
        _build(limits)


def test_build_context_budget_rejects_a_window_too_small_for_a_license() -> None:
    limits = ModelLimits("tiny-window", context_window=4_000, max_output_tokens=None)

    with pytest.raises(ValueError, match=r"context window .* is too small"):
        _build(limits)
