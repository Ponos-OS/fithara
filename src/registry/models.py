from __future__ import annotations

from pydantic import ConfigDict

from src.utils import CamelModel


class CanonicalLicense(CamelModel):
    """A single canonical license loaded from `src/licenses/*.md`."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    short_name: str
    version: str
    category: str
    official_url: str
    summary: str
    permissions: list[str]
    limitations: list[str]
    conditions: list[str]
    active: bool
    order: int
    body_markdown: str
