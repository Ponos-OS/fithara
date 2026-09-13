from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.modules.licenses import router as licenses_router
from src.registry import get_registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    get_registry()  # forces the registry load; a malformed file aborts startup (§3.2)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Fithara", lifespan=lifespan)
    app.include_router(licenses_router)

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Return `exc.detail` as the body verbatim (§4.10's error envelope), not FastAPI's default `{"detail": ...}` wrapper."""

        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    return app


app = create_app()
