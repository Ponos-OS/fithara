from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import Field

from src.utils import (
    CamelModel,
    ModelLimits,
    Settings,
    get_model_limits,
    get_settings,
    read_app_version,
)


router = APIRouter(tags=["health"])


class LlmLimits(CamelModel):
    """The model behind the drafting assistant and the window it works within. Never includes provider credentials or URLs."""

    model: str = Field(examples=["gpt-5.2"])
    context_window: int | None = Field(
        examples=[400000],
        description="Tokens the model can take, prompt and response together, from the model capability catalog. Null when the catalog does not know it.",
    )
    max_output_tokens: int | None = Field(
        examples=[128000],
        description="The most tokens the model can answer with, from the model capability catalog. Null when the catalog does not know it.",
    )


class Health(CamelModel):
    """Liveness plus what a caller needs to size its requests."""

    status: Literal["ok"]
    version: str = Field(examples=["1.1.0"])
    llm: LlmLimits


@router.get("/health", response_model=Health)
def health(
    settings: Settings = Depends(get_settings),
    limits: ModelLimits = Depends(get_model_limits),
) -> Health:
    return Health(
        status="ok",
        version=read_app_version(),
        llm=LlmLimits(
            model=settings.llm.model,
            context_window=limits.context_window,
            max_output_tokens=limits.max_output_tokens,
        ),
    )
