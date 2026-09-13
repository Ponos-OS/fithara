from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import (
    ValidationError as JsonSchemaValidationError,
    validate as validate_json_schema,
)
from pydantic import ValidationError

from src.registry.models import CanonicalLicense
from src.utils.config import get_settings


class RegistryLoadError(Exception):
    """Raised when the canonical license registry cannot be loaded."""


def _strip_formatting_fence(body: str) -> str:
    """
    The whole body of a license must be in a fenced code block.
    To stop IDEs from formatting it.
    Stripped from the coding block before the body is served.
    """
    code_fence_re = re.compile(r"\A```[^\n]*\n(.*)\n```\Z", re.DOTALL)

    match = code_fence_re.match(body)

    return match.group(1) if match else body


def _parse_file(path: Path, schema: dict) -> CanonicalLicense:
    frontmatter_re = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
    match = frontmatter_re.match(path.read_text(encoding="utf-8"))

    if not match:
        raise RegistryLoadError(f"{path}: missing YAML frontmatter delimited by '---'")

    frontmatter_raw, body = match.groups()
    frontmatter = yaml.safe_load(frontmatter_raw)

    try:
        validate_json_schema(frontmatter, schema)
    except JsonSchemaValidationError as exc:
        raise RegistryLoadError(
            f"{path}: frontmatter failed schema validation: {exc.message}"
        ) from exc

    body_markdown = _strip_formatting_fence(body.strip())

    try:
        return CanonicalLicense.model_validate({**frontmatter, "body_markdown": body_markdown})
    except ValidationError as exc:
        raise RegistryLoadError(f"{path}: {exc}") from exc


def load_registry(licenses_dir: Path) -> tuple[CanonicalLicense, ...]:
    """
    Load and validate all canonical licenses under `licenses_dir`.

    Raises `RegistryLoadError` on any malformed file or duplicate id.
    The caller (app startup) must let this propagate rather than log-and-continue.
    """
    schema = json.loads((licenses_dir / "_schema.json").read_text(encoding="utf-8"))
    licenses = [_parse_file(path, schema) for path in sorted(licenses_dir.glob("*.md"))]
    seen_ids: set[str] = set()

    for license_ in licenses:
        if license_.id in seen_ids:
            raise RegistryLoadError(f"duplicate canonical license id: {license_.id}")

        seen_ids.add(license_.id)

    return tuple(licenses)


@lru_cache(maxsize=1)
def get_registry() -> tuple[CanonicalLicense, ...]:
    """
    Return the process-wide registry, loaded once from `Settings.registry.path`.

    A FastAPI dependency, overridable in tests via `app.dependency_overrides`.
    """

    return load_registry(get_settings().registry.path)
