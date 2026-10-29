"""
The PydanticAI agent behind `POST /v1/draft`.

Exposes the canonical registry to the LLM as tools and forces its output
into the `DraftReply` shape. PydanticAI retries once on its own (its
default output-validation retry budget) when the LLM's structured output
fails to validate; if the retry also fails, `run_draft_agent` catches the
resulting `AgentRunError` and returns a safe, schema-valid fallback
response instead of raising.

`get_agent()`/`build_agent()` are deliberately lazy: nothing here reads
`Settings` or the prompt file at import time, so importing this module
(even once it's wired into `main.py`) stays side-effect-free.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic_ai import Agent, AgentRunError, ModelHTTPError, ModelRetry
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from src.modules.draft.compaction import (
    SUMMARY_TOKENS,
    clip,
    compact_history,
    load_compaction_prompt,
    render_turn,
)
from src.modules.draft.context import ContextBudget, build_context_budget, estimate_tokens
from src.modules.draft.model import build_model
from src.modules.draft.rules import canonical_text_matches
from src.modules.draft.types import ConversationTurn, DraftReply, DraftRequest, DraftResponse
from src.registry import CanonicalLicense, active_licenses_by_order, get_registry
from src.utils import api_error, get_model_limits, get_settings


_logger = logging.getLogger(__name__)
_PROMPT_PATH = Path(__file__).parent / "prompts" / "v1.md"
_FALLBACK_RESPONSE = DraftResponse(
    conversation=[],
    assistant_message=(
        "Sorry, I wasn't able to produce a reliable answer for that. "
        "Please try rephrasing your request."
    ),
    draft=None,
    draft_changed=False,
    recommendations=[],
    disclaimers=[
        "This is not legal advice. Consult a qualified lawyer before relying on this draft."
    ],
    is_ready_to_finalize=False,
)


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_agent(model: str | Model) -> Agent[None, DraftReply]:
    """
    Build a drafting agent for the given model.

    Production uses `get_agent()`. Tests pass `"test"` (PydanticAI's no-op
    sentinel model) or a `TestModel`/`FunctionModel` instance directly, then
    `.override(model=...)` to control what it returns — no settings or API
    key needed.
    """

    agent: Agent[None, DraftReply] = Agent(model, output_type=DraftReply)

    @agent.instructions
    def _instructions() -> str:
        return _load_system_prompt()

    @agent.tool_plain
    def list_canonical_licenses() -> list[dict[str, object]]:
        """List the canonical licenses currently offered to users."""

        return [
            license_.model_dump(by_alias=True, exclude={"body_markdown"})
            for license_ in active_licenses_by_order(get_registry())
        ]

    @agent.tool_plain
    def get_canonical_license(id: str) -> dict[str, object]:
        """Fetch one canonical license's full metadata and verbatim body by id."""

        for license_ in get_registry():
            if license_.id == id:
                return license_.model_dump(by_alias=True)

        raise ModelRetry(
            f"Unknown canonical license id: {id!r}. Call list_canonical_licenses to see valid ids."
        )

    return agent


@lru_cache(maxsize=1)
def get_agent() -> Agent[None, DraftReply]:
    """The process-wide production agent, built from `Settings.llm`."""

    return build_agent(build_model(get_settings().llm))


@lru_cache(maxsize=1)
def get_context_budget() -> ContextBudget:
    """What the configured model's context window leaves for a call. Raises when it leaves nothing."""

    settings = get_settings()

    return build_context_budget(
        get_model_limits(),
        settings.conversation,
        instructions=_load_system_prompt(),
        compaction_instructions=load_compaction_prompt(),
        summary_tokens=SUMMARY_TOKENS,
        registry=get_registry(),
    )


def _passes_canonical_integrity_check(
    response: DraftReply, registry: tuple[CanonicalLicense, ...]
) -> bool:
    """
    Rule 1's enforcement point: a draft claiming `source.type == "canonical"`
    must byte-equal the canonical body it claims to be — whether that's an
    honest mistake or a successful prompt injection, the effect is the same
    and the response must not reach the client as-is.
    """

    if response.draft is None or response.draft.source.type != "canonical":
        return True

    canonical_id = response.draft.source.canonical_id
    if canonical_id is None:
        return False

    for license_ in registry:
        if license_.id == canonical_id:
            return canonical_text_matches(response.draft, license_.body_markdown)

    return False


def _safe_error_fields(exc: AgentRunError) -> dict[str, object]:
    """
    Fields safe to log for an agent failure.

    Deliberately never includes `str(exc)` or a `ModelHTTPError.body` — a
    provider's HTTP error body can echo back request details, including the
    API key we just sent it (confirmed against a real 401 response: OpenAI's
    error body repeats the invalid key verbatim). No secrets in logs, full stop.
    """

    fields: dict[str, object] = {"error_type": type(exc).__name__}
    if isinstance(exc, ModelHTTPError):
        fields["status_code"] = exc.status_code
        fields["model_name"] = exc.model_name
    return fields


def _build_prompt(request: DraftRequest, conversation: list[ConversationTurn] | None = None) -> str:
    """
    The draft is its own block after the history and is never compacted: only `conversation` is.
    """

    turns = request.conversation if conversation is None else conversation
    lines = [render_turn(turn) for turn in turns]

    if request.draft is not None:
        lines.append(
            f"Current draft (source type: {request.draft.source.type}):\n{request.draft.text}"
        )
    if request.preferences is not None and request.preferences.category is not None:
        lines.append(f"Preferred category: {request.preferences.category}")

    lines.append(render_turn(ConversationTurn(role="user", content=request.message)))

    return "\n\n".join(lines)


def needs_compaction(request: DraftRequest, budget: ContextBudget) -> bool:
    """
    True when the prompt, built from the whole history, would not leave room for the response, or
    when the history sent back (this turn's two turns added) would be over the turn limit.
    """

    return (
        estimate_tokens(_build_prompt(request)) > budget.prompt_tokens
        or len(request.conversation) + 2 > budget.max_turns
    )


async def run_draft_agent(
    request: DraftRequest,
    *,
    agent: Agent[None, DraftReply] | None = None,
    registry: tuple[CanonicalLicense, ...] | None = None,
    compact: bool = False,
    budget: ContextBudget | None = None,
    compaction_agent: Agent[None, str] | None = None,
) -> DraftResponse:
    """
    Run the drafting agent for one turn. Falls back to a safe response on any agent failure, with
    the incoming conversation handed back unchanged so the failed exchange is not kept. The only
    thing it raises is a 400 when the draft alone leaves no room for the conversation, even compacted.

    With `compact`, the history older than the newest turns is replaced by a summary turn; the draft
    and the new message always travel verbatim. The returned `conversation` is what the client
    sends next time.
    """

    agent = agent or get_agent()
    budget = budget or get_context_budget()
    fallback = _FALLBACK_RESPONSE.model_copy(update={"conversation": request.conversation})
    conversation = request.conversation

    if compact:
        try:
            conversation = await compact_history(
                conversation,
                keep_recent_turns=budget.keep_recent_turns,
                max_input_tokens=budget.compaction_input_tokens,
                max_turn_chars=budget.max_turn_chars,
                agent=compaction_agent,
            )
        except AgentRunError as exc:
            _logger.warning("draft_agent_compaction_failed", extra=_safe_error_fields(exc))
            return fallback

    prompt = _build_prompt(request, conversation)
    if estimate_tokens(prompt) > budget.prompt_tokens:
        raise api_error(
            "INVALID_REQUEST",
            "the draft and the conversation are too long for the model's context window",
        )

    try:
        result = await agent.run(
            prompt, model_settings=ModelSettings(max_tokens=budget.response_tokens)
        )
    except AgentRunError as exc:
        _logger.warning("draft_agent_llm_call_failed", extra=_safe_error_fields(exc))
        return fallback

    registry = registry if registry is not None else get_registry()
    if not _passes_canonical_integrity_check(result.output, registry):
        canonical_id = result.output.draft.source.canonical_id if result.output.draft else None
        _logger.warning(
            "draft_agent_canonical_integrity_check_failed",
            extra={"canonical_id": canonical_id},
        )
        return fallback

    return DraftResponse(
        **result.output.model_dump(),
        conversation=[
            *conversation,
            ConversationTurn(role="user", content=clip(request.message, budget.max_turn_chars)),
            ConversationTurn(
                role="assistant",
                content=clip(result.output.assistant_message, budget.max_turn_chars),
            ),
        ],
    )
