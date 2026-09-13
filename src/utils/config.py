from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Llm(BaseModel):
    """LLM provider configuration for the PydanticAI drafting agent."""

    provider: str = Field(
        description="PydanticAI provider identifier, e.g. 'openai' or 'anthropic'."
    )
    model: str = Field(description="Model name for the drafting agent, e.g. 'gpt-5.2'.")
    api_key: str = Field(description="Provider API key.")
    timeout_ms: int = Field(default=30_000, ge=1_000)


class Registry(BaseModel):
    """
    Canonical license registry configuration.

    A plain `BaseModel`, not `BaseSettings`: a nested `BaseSettings` reads the
    whole process environment independently of its parent (case-insensitively,
    so `path` would match the ubiquitous `PATH` var) instead of only the
    `REGISTRY__` slice `Settings.env_nested_delimiter` carves out for it.
    """

    path: Path = Field(
        default=Path("./src/licenses"), description="Directory of canonical license Markdown files."
    )


class RateLimit(BaseModel):
    """Per-key/IP rate limiting. No retained content — counters only."""

    per_minute: int = Field(default=60, ge=1)


class Conversation(BaseModel):
    """Bounds on client-supplied conversation input, enforced on `POST /v1/draft`."""

    max_turns: int = Field(
        default=50, ge=1, description="Maximum entries allowed in `conversation`."
    )
    max_message_chars: int = Field(
        default=4_000,
        ge=1,
        description="Maximum characters allowed in `message` or any turn's `content`.",
    )


class Settings(BaseSettings):
    """Runtime configuration surface."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",
    )

    port: int = Field(default=8000, description="HTTP port to bind.")

    llm: Llm = Field(default_factory=Llm)  # pyright: ignore[reportArgumentType]
    registry: Registry = Field(default_factory=Registry)
    rate_limit: RateLimit = Field(default_factory=RateLimit)
    conversation: Conversation = Field(default_factory=Conversation)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` singleton."""

    return Settings()
