from __future__ import annotations

from pydantic_ai.models import Model, infer_model
from pydantic_ai.providers import infer_provider_class

from src.utils import Llm


def build_model(settings: Llm) -> Model:
    """
    A model string alone (`Agent("openai:gpt-5.2")`) makes PydanticAI build its
    own provider client from that provider's conventional env var (e.g.
    `OPENAI_API_KEY`), ignoring `Settings.llm.api_key` entirely. Building the
    provider explicitly with our own `api_key` is what actually wires the
    configured key up.
    """

    provider_kwargs: dict[str, object] = {"api_key": settings.api_key}
    if settings.base_url is not None:
        provider_kwargs["base_url"] = settings.base_url
    provider = infer_provider_class(settings.provider)(**provider_kwargs)  # pyright: ignore[reportCallIssue]

    return infer_model(f"{settings.provider}:{settings.model}", provider_factory=lambda _: provider)
