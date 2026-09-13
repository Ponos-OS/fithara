from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    registry: Registry = Field(default_factory=Registry)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` singleton."""

    return Settings()
