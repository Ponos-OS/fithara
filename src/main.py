from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.modules.draft import router as draft_router
from src.modules.licenses import router as licenses_router
from src.registry import get_registry
from src.utils import ErrorDetail, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    get_registry()  # forces the registry load; a malformed license file aborts startup
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Fithara", lifespan=lifespan)

    app.include_router(licenses_router)
    app.include_router(draft_router)

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Return `exc.detail` as the body verbatim, not FastAPI's default `{"detail": ...}` wrapper."""

        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Map FastAPI's default 422 request-validation failures onto the service's
        error envelope (400 INVALID_REQUEST).

        Built from `exc.errors()`, not `str(exc)` — the latter includes an
        internal traceback fragment (source file path, line number) that has
        no business being in a response sent to a client.
        """

        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        error = ErrorResponse(error=ErrorDetail(code="INVALID_REQUEST", message=details))
        return JSONResponse(status_code=400, content=error.model_dump(by_alias=True))

    return app


app = create_app()
