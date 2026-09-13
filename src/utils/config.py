from __future__ import annotations

import tomllib
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingMode(StrEnum):
    JSON = "JSON"
    PLAIN_TEXT = "PLAIN_TEXT"


class LogLevel(StrEnum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class Logging(BaseModel):
    """Structured JSON logs (prod) or plain-text logs (dev)."""

    mode: LoggingMode = Field(default=LoggingMode.JSON)
    level: LogLevel = Field(default=LogLevel.INFO)


class Otel(BaseModel):
    """
    OpenTelemetry tracing. Off by default — enabling it needs a real OTLP
    collector to send spans to (`exporter_otlp_endpoint`), so unlike `Llm`
    this isn't required: a service with tracing off is a legitimate,
    common state (a laptop with no collector running), not a
    misconfiguration.
    """

    enabled: bool = Field(default=False, description="Turn on OTel trace export.")
    exporter_otlp_endpoint: str = Field(
        default="http://localhost:4318",
        description="OTLP/HTTP collector base URL (spans go to '<this>/v1/traces').",
    )
    traces_sampler: str = Field(default="parentbased_always_on")


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
    service_name: str = Field(
        default="fithara", description="Reported to OTel and used as a general service identifier."
    )

    llm: Llm = Field(default_factory=Llm)  # pyright: ignore[reportArgumentType]
    registry: Registry = Field(default_factory=Registry)
    rate_limit: RateLimit = Field(default_factory=RateLimit)
    conversation: Conversation = Field(default_factory=Conversation)
    logging: Logging = Field(default_factory=Logging)
    otel: Otel = Field(default_factory=Otel)

    @property
    def app_version(self) -> str:
        """Read `[project].version` from pyproject.toml at runtime."""

        pyproject = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

        return data["project"]["version"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` singleton."""

    return Settings()
