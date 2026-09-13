"""Public API for src.registry — the canonical license registry."""

from __future__ import annotations

from src.registry.loader import (
    RegistryLoadError,
    active_licenses_by_order,
    get_registry,
    load_registry,
)
from src.registry.models import CanonicalLicense


__all__ = [
    "CanonicalLicense",
    "RegistryLoadError",
    "active_licenses_by_order",
    "get_registry",
    "load_registry",
]
