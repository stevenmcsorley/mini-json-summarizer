"""FastAPI application factory and global exception handling."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import __version__ as app_version
from app.api.routes import router
from app.config import get_settings


def create_application() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()
    app = FastAPI(
        title="Mini JSON Summarizer",
        description="Deterministic-first summarizer for large JSON payloads.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "validation_error", "details": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            payload = detail
        elif detail == "There was an error parsing the body":
            payload = {"error": "invalid_json", "details": detail}
        else:
            payload = {"error": "http_error", "details": detail}
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "engine": "deterministic",
            "version": app_version,
            "max_payload_bytes": settings.max_payload_bytes,
        }

    app.include_router(router)
    return app


app = create_application()
