from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import llmcapa

from src.utils.config import get_settings


_logger = logging.getLogger(__name__)

# The catalog's provider ids; any other provider (e.g. a self-hosted Ollama) is searched across the whole catalog.
PROVIDER_IN_LLMCAPA = {"openai": "openai", "anthropic": "anthropic"}
# Models the catalog lacks, by lowercase id: (context window, maximum output tokens).
HARDCODED_LIMITS: dict[str, tuple[int, int]] = {}


@dataclass(frozen=True)
class ModelLimits:
    model: str
    context_window: int | None = None
    max_output_tokens: int | None = None


def model_limits(model_id: str, provider: str | None = None) -> ModelLimits:
    """
    What the offline catalog, then the hardcoded table, knows about the model.

    A limit nobody publishes is `None`. `llmcapa.get` fetches a catalog from GitHub on a
    provider-scoped miss, so the catalog is searched through `list_models`, which never touches
    the network.
    """

    wanted = model_id.casefold()
    try:
        known = llmcapa.list_models(PROVIDER_IN_LLMCAPA.get(provider or ""))
        capability = next(
            c
            for c in known
            if wanted in (c.model_id.casefold(), *(a.casefold() for a in c.aliases))
        )
    except StopIteration:
        _logger.error("model_not_in_catalog", extra={"model": model_id, "provider": provider})
        return _hardcoded(model_id)
    except Exception:
        _logger.exception(
            "model_catalog_lookup_failed", extra={"model": model_id, "provider": provider}
        )
        return _hardcoded(model_id)

    return ModelLimits(
        model_id, capability.context_window or None, capability.max_output_tokens or None
    )


def _hardcoded(model_id: str) -> ModelLimits:
    window, max_output = HARDCODED_LIMITS.get(model_id.casefold(), (None, None))

    return ModelLimits(model_id, window, max_output)


@lru_cache(maxsize=1)
def get_model_limits() -> ModelLimits:
    """The limits of the configured model."""

    llm = get_settings().llm

    return model_limits(llm.model, llm.provider)
