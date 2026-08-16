"""FastAPI application. One process, SQLite, asyncio HTTP, background campaigns."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from searcher.api.capabilities import router as capabilities_router
from searcher.api.deletion import router as deletion_router
from searcher.api.dependencies import ApiError, AppState, build_state, find_web_root
from searcher.api.events import router as events_router
from searcher.api.feedback import router as feedback_router
from searcher.api.health import router as health_router
from searcher.api.logging import RequestLogMiddleware, configure_logging
from searcher.api.results import router as results_router
from searcher.api.searches import router as searches_router
from searcher.core.config import Settings
from searcher.core.errors import SearcherError


def _error_body(error: str, detail: str) -> dict[str, str]:
    return {"error": error, "detail": detail}


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    configure_logging()
    state = build_state(cfg)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.searcher = state
        try:
            yield
        finally:
            held: AppState = app.state.searcher
            for search_id in list(held.threads):
                held.controller.cancellation.request(search_id)
            for thread in list(held.threads.values()):
                if thread.is_alive():
                    thread.join(timeout=1.0)
            held.db.close()

    app = FastAPI(
        title="Searcher API",
        version="v1",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.searcher = state
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Last-Event-ID", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Type"],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error, exc.detail),
        )

    @app.exception_handler(SearcherError)
    async def searcher_error_handler(_request: Request, exc: SearcherError) -> JSONResponse:
        detail = str(exc)
        if "search_id=" in detail:
            detail = detail.split("search_id=", 1)[0].rstrip(" (").strip()
        if detail.startswith("["):
            closing = detail.find("]")
            if closing != -1:
                detail = detail[closing + 1 :].strip()
        return JSONResponse(status_code=422, content=_error_body("validation", detail))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        del exc
        return JSONResponse(
            status_code=422,
            content=_error_body("validation", "The request did not match the expected fields."),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        error = "not_found" if exc.status_code == 404 else "error"
        return JSONResponse(status_code=exc.status_code, content=_error_body(error, detail))

    app.include_router(health_router)
    app.include_router(capabilities_router)
    app.include_router(searches_router)
    app.include_router(events_router)
    app.include_router(results_router)
    app.include_router(feedback_router)
    app.include_router(deletion_router)

    if cfg.serve_web:
        web_root = find_web_root()
        if web_root is not None:
            # DEV ONLY: local UI mount so config.js API_BASE="" works unchanged.
            app.mount(
                "/",
                StaticFiles(directory=str(web_root), html=True),
                name="web-dev-only",
            )

    return app


def run_server(settings: Settings | None = None) -> None:
    cfg = settings or Settings.from_env()
    app = create_app(cfg)
    uvicorn.run(
        app,
        host=cfg.api_host,
        port=cfg.api_port,
        log_config=None,
        access_log=False,
    )


def app_from_env() -> FastAPI:
    return create_app()


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
