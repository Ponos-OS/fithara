"""
The PydanticAI agent behind `POST /v1/draft`.

Exposes the canonical registry to the LLM as tools and forces its output
into the `DraftResponse` shape. PydanticAI retries once on its own (its
default output-validation retry budget) when the LLM's structured output
fails to validate; if the retry also fails, `run_draft_agent` catches the
resulting `AgentRunError` and returns a safe, schema-valid fallback
response instead of raising.

`get_agent()`/`build_agent()` are deliberately lazy: nothing here reads
`Settings` or the prompt file at import time, so importing this module
(even once it's wired into `main.py`) stays side-effect-free.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_ai import Agent, AgentRunError, ModelRetry
from pydantic_ai.models import Model, infer_model
from pydantic_ai.providers import infer_provider_class

from src.modules.draft.rules import canonical_text_matches
from src.modules.draft.types import ConversationTurn, DraftRequest, DraftResponse
from src.registry import CanonicalLicense, active_licenses_by_order, get_registry
from src.utils import get_settings


_PROMPT_PATH = Path(__file__).parent / "prompts" / "v1.md"
_FALLBACK_RESPONSE = DraftResponse(
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


def build_agent(model: str | Model) -> Agent[None, DraftResponse]:
    """
    Build a drafting agent for the given model.

    Production uses `get_agent()`. Tests pass `"test"` (PydanticAI's no-op
    sentinel model) or a `TestModel`/`FunctionModel` instance directly, then
    `.override(model=...)` to control what it returns — no settings or API
    key needed.
    """

    agent: Agent[None, DraftResponse] = Agent(model, output_type=DraftResponse)

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
def get_agent() -> Agent[None, DraftResponse]:
    """
    The process-wide production agent, built from `Settings.llm`.

    A model string alone (`Agent("openai:gpt-5.2")`) makes PydanticAI build its
    own provider client from that provider's conventional env var (e.g.
    `OPENAI_API_KEY`), ignoring `Settings.llm.api_key` entirely. Building the
    provider explicitly with our own `api_key` is what actually wires the
    configured key up.
    """

    settings = get_settings().llm
    provider = infer_provider_class(settings.provider)(
        api_key=settings.api_key  # pyright: ignore[reportCallIssue]
    )
    model = infer_model(
        f"{settings.provider}:{settings.model}", provider_factory=lambda _: provider
    )
    return build_agent(model)


def _passes_canonical_integrity_check(
    response: DraftResponse, registry: tuple[CanonicalLicense, ...]
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


def _turn_line(turn: ConversationTurn) -> str:
    return f"{turn.role}: {turn.content}"


def _build_prompt(request: DraftRequest) -> str:
    lines = [_turn_line(turn) for turn in request.conversation]

    if request.draft is not None:
        lines.append(
            f"Current draft (source type: {request.draft.source.type}):\n{request.draft.text}"
        )
    if request.preferences is not None and request.preferences.category is not None:
        lines.append(f"Preferred category: {request.preferences.category}")

    lines.append(_turn_line(ConversationTurn(role="user", content=request.message)))

    return "\n\n".join(lines)


async def run_draft_agent(
    request: DraftRequest,
    *,
    agent: Agent[None, DraftResponse] | None = None,
    registry: tuple[CanonicalLicense, ...] | None = None,
) -> DraftResponse:
    """Run the drafting agent for one turn. Never raises — falls back to a safe response on any agent failure."""

    agent = agent or get_agent()

    try:
        result = await agent.run(_build_prompt(request))
    except AgentRunError:
        return _FALLBACK_RESPONSE

    registry = registry if registry is not None else get_registry()
    if not _passes_canonical_integrity_check(result.output, registry):
        return _FALLBACK_RESPONSE

    return result.output
