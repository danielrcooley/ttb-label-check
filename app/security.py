"""Security headers, request ids, body-size guard, per-client in-flight cap, error envelope."""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import Settings
from app.ocr.pool import BusyError
from app.pipeline.images import ImageError
from app.schemas import ErrorResponse

log = logging.getLogger("app.request")

CSP = (
    "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "") or ""


def error_response(
    status: int,
    code: str,
    message: str,
    hint: str | None = None,
    request_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, hint=hint, request_id=request_id).model_dump()
    return JSONResponse(status_code=status, content=body, headers=headers)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Request id + security headers + Content-Length guard. Logs method, path, status, ms only."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = uuid.uuid4().hex[:12]
        request.state.request_id = rid
        if request.method in ("POST", "PUT", "PATCH"):
            length = request.headers.get("content-length")
            if length is None:
                return error_response(411, "length_required", "Uploads must declare Content-Length.", request_id=rid)
            if int(length) > self.settings.max_request_bytes:
                mb = self.settings.max_request_bytes // (1024 * 1024)
                return error_response(
                    413,
                    "request_too_large",
                    f"The upload is larger than the {mb} MB request limit.",
                    "Send fewer or smaller images per request.",
                    request_id=rid,
                )
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = CSP
        response.headers.setdefault("Cache-Control", "no-store")
        return response


class ClientLimiter:
    """Caps concurrent requests per client so one script cannot monopolize the pool."""

    def __init__(self, settings: Settings) -> None:
        self.limit = settings.per_client_inflight
        self.trust_proxy = settings.trust_proxy
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}

    def client_id(self, request: Request) -> str:
        if self.trust_proxy:
            fwd = request.headers.get("x-forwarded-for")
            if fwd:
                return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    @asynccontextmanager
    async def slot(self, request: Request) -> AsyncIterator[None]:
        cid = self.client_id(request)
        with self._lock:
            if self._counts.get(cid, 0) >= self.limit:
                raise HTTPException(status_code=429, detail="too_many_inflight", headers={"Retry-After": "1"})
            self._counts[cid] = self._counts.get(cid, 0) + 1
        try:
            yield
        finally:
            with self._lock:
                self._counts[cid] -= 1
                if self._counts[cid] <= 0:
                    del self._counts[cid]


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ImageError)
    async def _image_error(request: Request, exc: ImageError) -> JSONResponse:
        status = {"unsupported_format": 415, "image_too_large": 413}.get(exc.code, 400)
        return error_response(status, exc.code, exc.message, exc.hint, request_id_of(request))

    @app.exception_handler(BusyError)
    async def _busy(request: Request, exc: BusyError) -> JSONResponse:
        return error_response(
            429,
            "busy",
            "The verification service is at capacity right now.",
            "Retry in a moment; batch clients back off automatically.",
            request_id_of(request),
            headers={"Retry-After": str(exc.retry_after)},
        )

    @app.exception_handler(HTTPException)
    async def _http(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "error"
        messages = {
            "too_many_inflight": (
                "Too many requests in flight from this client.",
                "Limit concurrent uploads and retry shortly.",
            ),
            "not_ready": ("The OCR engine is still starting.", "Retry in a few seconds."),
        }
        message, hint = messages.get(detail, (detail, None))
        return error_response(exc.status_code, detail, message, hint, request_id_of(request), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p not in ("body",))
        return error_response(
            422,
            "invalid_request",
            f"{loc or 'request'}: {first.get('msg', 'invalid')}",
            "Check the field names and values.",
            request_id_of(request),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error rid=%s", request_id_of(request))
        return error_response(
            500,
            "internal_error",
            "Something went wrong on our side.",
            "Try again; if it persists, report the request id.",
            request_id_of(request),
        )
