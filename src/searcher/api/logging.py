"""Structured JSON request logs. No uploads, filenames, paths, or secrets."""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from searcher.core.ids import new_id
from searcher.core.time import format_utc, utc_now

_SAFE_PATH_PREFIXES = ("/v1/", "/health")
_log = logging.getLogger("searcher.api")


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _log.handlers.clear()
    _log.addHandler(handler)
    _log.setLevel(logging.INFO)
    _log.propagate = False


def _safe_path(path: str) -> str:
    if path.startswith(_SAFE_PATH_PREFIXES) or path == "/v1/health":
        return path.split("?", 1)[0]
    if path.startswith("/"):
        return "/static"
    return "/unknown"


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or new_id()
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            _log.info(
                json.dumps(
                    {
                        "ts": format_utc(utc_now()),
                        "level": "error",
                        "request_id": request_id,
                        "method": request.method,
                        "path": _safe_path(request.url.path),
                        "status": 500,
                        "ms": elapsed_ms,
                    },
                    sort_keys=True,
                )
            )
            raise
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        _log.info(
            json.dumps(
                {
                    "ts": format_utc(utc_now()),
                    "level": "info",
                    "request_id": request_id,
                    "method": request.method,
                    "path": _safe_path(request.url.path),
                    "status": response.status_code,
                    "ms": elapsed_ms,
                },
                sort_keys=True,
            )
        )
        return response
