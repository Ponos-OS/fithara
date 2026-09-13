"""Public API for src.modules.licenses — browsing the canonical registry over HTTP."""

from __future__ import annotations

from src.modules.licenses.routes import (
    LicenseDetail,
    LicenseListResponse,
    LicenseSummary,
    router,
)


__all__ = [
    "LicenseDetail",
    "LicenseListResponse",
    "LicenseSummary",
    "router",
]
