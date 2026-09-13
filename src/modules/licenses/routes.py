from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import Field

from src.registry import CanonicalLicense, active_licenses_by_order, get_registry
from src.utils import CamelModel, ErrorResponse, api_error


router = APIRouter(tags=["licenses"])


class LicenseSummary(CamelModel):
    """Canonical license metadata, without the (large) body text."""

    id: str = Field(examples=["CC-BY-NC-4.0"], description="Stable machine-readable identifier.")
    name: str = Field(examples=["Creative Commons Attribution-NonCommercial 4.0 International"])
    short_name: str = Field(examples=["CC BY-NC 4.0"])
    version: str = Field(examples=["4.0"])
    category: str = Field(examples=["creative_commons"])
    official_url: str = Field(
        examples=["https://creativecommons.org/licenses/by-nc/4.0/legalcode"],
        description="Link to the authoritative license text.",
    )
    summary: str = Field(
        examples=[
            "Allows others to share and adapt the work for non-commercial purposes, "
            "provided they give appropriate credit."
        ]
    )
    permissions: list[str] = Field(examples=[["share", "adapt"]])
    limitations: list[str] = Field(examples=[["non_commercial"]])
    conditions: list[str] = Field(examples=[["attribution"]])


class LicenseDetail(LicenseSummary):
    """Canonical license metadata plus its verbatim body."""

    body: str = Field(
        examples=["# Creative Commons Attribution-NonCommercial 4.0 International\n\n..."],
        description="The verbatim canonical license text, as Markdown. Never paraphrased.",
    )


class LicenseListResponse(CamelModel):
    """The set of licenses currently offered to users."""

    licenses: list[LicenseSummary]


def _to_summary(license_: CanonicalLicense) -> LicenseSummary:
    return LicenseSummary.model_validate(license_.model_dump(by_alias=True))


def _to_detail(license_: CanonicalLicense) -> LicenseDetail:
    return LicenseDetail.model_validate(
        {**license_.model_dump(by_alias=True), "body": license_.body_markdown}
    )


def find_license_or_error(
    registry: tuple[CanonicalLicense, ...], license_id: str
) -> CanonicalLicense:
    """
    Look up a license by id.

    Raises `UNKNOWN_LICENSE` (404) if the id was never registered, or
    `LICENSE_INACTIVE` (410) if it's registered but retired — retired ids
    stay resolvable here (for existing drafts referencing them) but drop
    out of `GET /v1/licenses` and can't be selected for new drafts.
    """

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
                "The license id is registered but retired: it no longer appears in "
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
