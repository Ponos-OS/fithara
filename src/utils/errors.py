from __future__ import annotations

from typing import Literal

from fastapi import HTTPException
from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


ErrorCode = Literal[
    "INVALID_REQUEST",
    "UNKNOWN_LICENSE",
    "LICENSE_INACTIVE",
    "RATE_LIMITED",
    "LLM_UNAVAILABLE",
    "LLM_INVALID_OUTPUT",
    "INTERNAL",
]

_STATUS_BY_CODE: dict[ErrorCode, int] = {
    "INVALID_REQUEST": 400,
    "UNKNOWN_LICENSE": 404,
    "LICENSE_INACTIVE": 410,
    "RATE_LIMITED": 429,
    "LLM_UNAVAILABLE": 503,
    "LLM_INVALID_OUTPUT": 502,
    "INTERNAL": 500,
}


class ErrorDetail(BaseModel):
    model_config = ConfigDict(
        alias_generator=AliasGenerator(validation_alias=to_camel, serialization_alias=to_camel),
        populate_by_name=True,
    )

    code: ErrorCode
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Wire shape for every error response this service returns."""

    error: ErrorDetail


def api_error(code: ErrorCode, message: str) -> HTTPException:
    """Build an `HTTPException` whose body matches `ErrorResponse`'s shape."""

    return HTTPException(
        status_code=_STATUS_BY_CODE[code],
        detail=ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump(
            by_alias=True
        ),
    )
