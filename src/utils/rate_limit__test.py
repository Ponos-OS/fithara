import pytest
from fastapi import HTTPException

from src.utils import ErrorResponse, RateLimiter


def test_rate_limiter_allows_hits_within_the_limit() -> None:
    limiter = RateLimiter(per_minute=2)

    limiter.check("client-a")  # act

    limiter.check("client-a")  # should not raise: still within the limit


def test_rate_limiter_rejects_hits_over_the_limit() -> None:
    limiter = RateLimiter(per_minute=1)
    limiter.check("client-a")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("client-a")

    assert exc_info.value.status_code == 429
    error = ErrorResponse.model_validate(exc_info.value.detail)
    assert error.error.code == "RATE_LIMITED"


def test_rate_limiter_tracks_keys_independently() -> None:
    limiter = RateLimiter(per_minute=1)
    limiter.check("client-a")

    limiter.check("client-b")  # act
