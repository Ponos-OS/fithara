from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema
from pydantic import ValidationError

from app.registry.models import CanonicalLicense

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


class RegistryLoadError(Exception):
    """Raised when the canonical license registry cannot be loaded (§3.2)."""


def _parse_file(path: Path, schema: dict) -> CanonicalLicense:
    match = _FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        raise RegistryLoadError(f"{path}: missing YAML frontmatter delimited by '---'")

    frontmatter_raw, body = match.groups()
    frontmatter = yaml.safe_load(frontmatter_raw)

    try:
        validate_json_schema(frontmatter, schema)
    except JsonSchemaValidationError as exc:
        raise RegistryLoadError(f"{path}: frontmatter failed schema validation: {exc.message}") from exc

    try:
        return CanonicalLicense.model_validate({**frontmatter, "body_markdown": body.strip()})
    except ValidationError as exc:
        raise RegistryLoadError(f"{path}: {exc}") from exc


def load_registry(licenses_dir: Path) -> tuple[CanonicalLicense, ...]:
    """Load and validate all canonical licenses under `licenses_dir` (§3.1-3.2).

    Raises `RegistryLoadError` on any malformed file or duplicate id — the
    caller (app startup) must let this propagate rather than log-and-continue.
    """
    schema = json.loads((licenses_dir / "_schema.json").read_text(encoding="utf-8"))

    licenses = [_parse_file(path, schema) for path in sorted(licenses_dir.glob("*.md"))]

    seen_ids: set[str] = set()
    for license_ in licenses:
        if license_.id in seen_ids:
            raise RegistryLoadError(f"duplicate canonical license id: {license_.id}")
        seen_ids.add(license_.id)

    return tuple(licenses)
