"""Security headers, request ids, body-size guard, admission caps before body parsing, error envelope."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping

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
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": CSP,
}
# Endpoints that parse bodies and cost CPU; capped before the body is read.
METERED_PREFIXES = ("/api/v1/verify", "/api/v1/extract", "/api/v1/compare", "/api/v1/csv/parse")


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "") or ""


def apply_security_headers(response: Response) -> Response:
    for k, v in SECURITY_HEADERS.items():
        response.headers[k] = v
    response.headers.setdefault("Cache-Control", "no-store")
    return response


def error_response(
    status: int,
    code: str,
    message: str,
    hint: str | None = None,
    request_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, hint=hint, request_id=request_id).model_dump()
    resp = JSONResponse(status_code=status, content=body, headers=dict(headers or {}))
    if request_id:
        resp.headers["X-Request-ID"] = request_id
    apply_security_headers(resp)
    return resp


class AdmissionLimiter:
    """Per-client and global caps on concurrent metered requests, enforced before body parsing.

    Client identity: the connection address, or, when ``trust_proxy`` is set, the LAST value of
    X-Forwarded-For, which is the one appended by the trusted ingress (the first value can be
    forged by the client).
    """

    def __init__(self, settings: Settings) -> None:
        self.per_client = settings.per_client_inflight
        self.global_limit = settings.global_inflight
        self.trust_proxy = settings.trust_proxy
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}
        self._total = 0

    def client_id(self, request: Request) -> str:
        if self.trust_proxy:
            fwd = request.headers.get("x-forwarded-for")
            if fwd:
                return fwd.split(",")[-1].strip()
        return request.client.host if request.client else "unknown"

    def acquire(self, request: Request) -> str | None:
        """Returns None when admitted, else the reason code."""
        cid = self.client_id(request)
        with self._lock:
            if self._total >= self.global_limit:
                return "service_busy"
            if self._counts.get(cid, 0) >= self.per_client:
                return "too_many_inflight"
            self._counts[cid] = self._counts.get(cid, 0) + 1
            self._total += 1
        request.state.admitted_client = cid
        return None

    def release(self, request: Request) -> None:
        cid = getattr(request.state, "admitted_client", None)
        if cid is None:
            return
        with self._lock:
            self._counts[cid] -= 1
            if self._counts[cid] <= 0:
                del self._counts[cid]
            self._total -= 1

    @property
    def in_flight(self) -> int:
        return self._total


class SecurityMiddleware(BaseHTTPMiddleware):
    """Request id, Content-Length guard, admission caps, security headers, Server-Timing.
    Logs method, path, status and milliseconds only."""

    def __init__(self, app: ASGIApp, settings: Settings, limiter: AdmissionLimiter) -> None:
        super().__init__(app)
        self.settings = settings
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = uuid.uuid4().hex[:12]
        request.state.request_id = rid
        t0 = time.perf_counter()
        metered = request.method == "POST" and request.url.path.startswith(METERED_PREFIXES)
        if request.method in ("POST", "PUT", "PATCH"):
            length = request.headers.get("content-length")
            if length is None:
                return error_response(411, "length_required", "Uploads must declare Content-Length.", request_id=rid)
            try:
                declared = int(length)
                if declared < 0:
                    raise ValueError
            except ValueError:
                return error_response(400, "bad_request", "Content-Length is not a valid number.", request_id=rid)
            if declared > self.settings.max_request_bytes:
                mb = self.settings.max_request_bytes // (1024 * 1024)
                return error_response(
                    413,
                    "request_too_large",
                    f"The upload is larger than the {mb} MB request limit.",
                    "Send fewer or smaller images per request.",
                    request_id=rid,
                )
        admitted = False
        if metered:
            reason = self.limiter.acquire(request)
            if reason == "too_many_inflight":
                return error_response(
                    429,
                    reason,
                    "Too many requests in flight from this client.",
                    "Limit concurrent uploads and retry shortly.",
                    request_id=rid,
                    headers={"Retry-After": "1"},
                )
            if reason == "service_busy":
                return error_response(
                    503,
                    reason,
                    "The service is handling as many requests as it can right now.",
                    "Retry in a moment.",
                    request_id=rid,
                    headers={"Retry-After": "2"},
                )
            admitted = True
        try:
            response = await call_next(request)
        finally:
            if admitted:
                self.limiter.release(request)
        response.headers["X-Request-ID"] = rid
        response.headers["Server-Timing"] = f"total;dur={(time.perf_counter() - t0) * 1000:.0f}"
        apply_security_headers(response)
        if request.url.path.startswith("/api/"):
            log.info(
                "%s %s %s %.0fms rid=%s",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - t0) * 1000,
                rid,
            )
        return response


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
            "not_ready": ("The OCR engine is still starting.", "Retry in a few seconds."),
        }
        hint: str | None
        if detail.startswith("warm-up failed"):
            message, hint = detail, "The service cannot start; see the container logs."
        else:
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
