from src.modules.draft import (
    Draft,
    DraftSource,
    canonical_text_matches,
    custom_has_no_canonical_id,
    draft_unchanged_when_not_changed,
    fork_is_labeled,
)


CANONICAL_BODY = "# CC BY 4.0\n\nVerbatim canonical text."
CANONICAL_NAME = "Creative Commons Attribution 4.0 International"


def test_canonical_text_matches_flags_byte_mismatch() -> None:
    draft = Draft(
        title=CANONICAL_NAME,
        text=CANONICAL_BODY + " edited",
        source=DraftSource(type="canonical", canonical_id="CC-BY-4.0"),
    )

    result = canonical_text_matches(draft, CANONICAL_BODY)  # act

    assert result is False


def test_canonical_text_matches_passes_on_byte_equal_body() -> None:
    draft = Draft(
        title=CANONICAL_NAME,
        text=CANONICAL_BODY,
        source=DraftSource(type="canonical", canonical_id="CC-BY-4.0"),
    )

    result = canonical_text_matches(draft, CANONICAL_BODY)  # act

    assert result is True


def test_fork_is_labeled_flags_unlabeled_fork() -> None:
    draft = Draft(
        title=CANONICAL_NAME,
        text=CANONICAL_BODY + " edited",
        source=DraftSource(type="canonical", canonical_id="CC-BY-4.0"),
    )

    result = fork_is_labeled(draft, CANONICAL_BODY, CANONICAL_NAME)  # act

    assert result is False


def test_fork_is_labeled_passes_on_forked_with_distinct_title() -> None:
    draft = Draft(
        title="Custom license (derived from CC BY 4.0)",
        text=CANONICAL_BODY + " edited",
        source=DraftSource(type="forked", canonical_id="CC-BY-4.0"),
    )

    result = fork_is_labeled(draft, CANONICAL_BODY, CANONICAL_NAME)  # act

    assert result is True


def test_custom_has_no_canonical_id_flags_custom_with_canonical_id() -> None:
    source = DraftSource(type="custom", canonical_id="CC-BY-4.0")

    result = custom_has_no_canonical_id(source)  # act

    assert result is False


def test_custom_has_no_canonical_id_passes_on_custom_without_canonical_id() -> None:
    source = DraftSource(type="custom")

    result = custom_has_no_canonical_id(source)  # act

    assert result is True


def test_draft_unchanged_when_not_changed_flags_mutated_on_explain() -> None:
    previous = Draft(title="t", text="body", source=DraftSource(type="custom"))
    mutated = Draft(title="t", text="different body", source=DraftSource(type="custom"))

    result = draft_unchanged_when_not_changed(previous, mutated, draft_changed=False)  # act

    assert result is False


def test_draft_unchanged_when_not_changed_passes_on_identical_draft() -> None:
    previous = Draft(title="t", text="body", source=DraftSource(type="custom"))
    same = previous.model_copy(deep=True)

    result = draft_unchanged_when_not_changed(previous, same, draft_changed=False)  # act

    assert result is True
