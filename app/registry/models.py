from __future__ import annotations

from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CanonicalLicense(BaseModel):
    """A single canonical license loaded from `app/licenses/*.md` (§3, §4.3)."""

    model_config = ConfigDict(
        alias_generator=AliasGenerator(validation_alias=to_camel, serialization_alias=to_camel),
        populate_by_name=True,
        frozen=True,
    )

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
