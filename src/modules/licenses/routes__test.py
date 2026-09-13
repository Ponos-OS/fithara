import pytest
from fastapi import HTTPException

from src.modules.licenses.routes import (
    active_licenses_by_order,
    find_license_or_error,
)
from src.registry.models import CanonicalLicense
from src.utils.errors import ErrorResponse


def _license(**overrides) -> CanonicalLicense:
    defaults = {
        "id": "EXAMPLE",
        "name": "Example License",
        "short_name": "Example",
        "version": "1.0",
        "category": "creative_commons",
        "official_url": "https://example.com/license",
        "summary": "An example.",
        "permissions": ["share"],
        "limitations": [],
        "conditions": ["attribution"],
        "active": True,
        "order": 10,
        "body_markdown": "Body text.",
    }
    return CanonicalLicense(**{**defaults, **overrides})


def test_active_licenses_by_order_excludes_inactive_and_sorts_by_order() -> None:
    registry = (
        _license(id="LOW", order=20),
        _license(id="INACTIVE", order=5, active=False),
        _license(id="HIGH", order=10),
    )

    result = active_licenses_by_order(registry)  # act

    assert [license_.id for license_ in result] == ["HIGH", "LOW"]


def test_find_license_or_error_returns_active_license() -> None:
    registry = (_license(id="ACTIVE-ONE"),)

    result = find_license_or_error(registry, "ACTIVE-ONE")  # act

    assert result.id == "ACTIVE-ONE"


def test_find_license_or_error_raises_404_for_unknown_id() -> None:
    registry = (_license(id="KNOWN"),)

    with pytest.raises(HTTPException) as exc_info:
        find_license_or_error(registry, "UNKNOWN")

    assert exc_info.value.status_code == 404
    error = ErrorResponse.model_validate(exc_info.value.detail)
    assert error.error.code == "UNKNOWN_LICENSE"


def test_find_license_or_error_raises_410_for_inactive_id() -> None:
    registry = (_license(id="RETIRED", active=False),)

    with pytest.raises(HTTPException) as exc_info:
        find_license_or_error(registry, "RETIRED")

    assert exc_info.value.status_code == 410
    error = ErrorResponse.model_validate(exc_info.value.detail)
    assert error.error.code == "LICENSE_INACTIVE"
