from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from src.registry import CanonicalLicense, get_registry
from src.utils import ErrorResponse, api_error


router = APIRouter(tags=["licenses"])


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=AliasGenerator(validation_alias=to_camel, serialization_alias=to_camel),
        populate_by_name=True,
    )


class LicenseSummary(_CamelModel):
    """Canonical license metadata, without the (large) body text."""

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


class LicenseDetail(LicenseSummary):
    """Canonical license metadata plus its verbatim body."""

    body: str


class LicenseListResponse(_CamelModel):
    licenses: list[LicenseSummary]


def _to_summary(license_: CanonicalLicense) -> LicenseSummary:
    return LicenseSummary.model_validate(license_.model_dump(by_alias=True))


def _to_detail(license_: CanonicalLicense) -> LicenseDetail:
    return LicenseDetail.model_validate(
        {**license_.model_dump(by_alias=True), "body": license_.body_markdown}
    )


def active_licenses_by_order(
    registry: tuple[CanonicalLicense, ...],
) -> list[CanonicalLicense]:
    """Active licenses only, ordered by `order` (§4.4)."""

    return sorted(
        (license_ for license_ in registry if license_.active), key=lambda license_: license_.order
    )


def find_license_or_error(
    registry: tuple[CanonicalLicense, ...], license_id: str
) -> CanonicalLicense:
    """Look up a license by id, raising the §4.10 error for unknown/inactive ids (§3.3)."""

    for license_ in registry:
        if license_.id == license_id:
            if not license_.active:
                raise api_error("LICENSE_INACTIVE", f"License is no longer offered: {license_id}")
            return license_

    raise api_error("UNKNOWN_LICENSE", f"Unknown license id: {license_id}")


@router.get("/v1/licenses", response_model=LicenseListResponse)
def list_licenses(
    registry: tuple[CanonicalLicense, ...] = Depends(get_registry),
) -> LicenseListResponse:
    return LicenseListResponse(
        licenses=[_to_summary(license_) for license_ in active_licenses_by_order(registry)]
    )


@router.get(
    "/v1/licenses/{license_id}",
    response_model=LicenseDetail,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Unknown license id — this service has never registered it.",
        },
        410: {
            "model": ErrorResponse,
            "description": (
                "The license id is registered but retired (§3.3): it no longer appears in "
                "`GET /v1/licenses` and cannot be selected for new drafts, but existing drafts "
                "referencing it still resolve via `POST /v1/draft`."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "LICENSE_INACTIVE",
                            "message": "License is no longer offered: CC-BY-4.0",
                        }
                    }
                }
            },
        },
    },
)
def get_license(
    license_id: str, registry: tuple[CanonicalLicense, ...] = Depends(get_registry)
) -> LicenseDetail:
    return _to_detail(find_license_or_error(registry, license_id))
