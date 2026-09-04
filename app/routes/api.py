from __future__ import annotations

import json
from typing import cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError

from app import __version__
from app.config import Settings
from app.ocr.pool import OcrPool
from app.pipeline.images import ImageError
from app.schemas import (
    ApplicationFields,
    CompareRequest,
    CompareResponse,
    CompareResponseItem,
    ExtractResponse,
    HealthResponse,
    VerifyResponse,
)
from app.security import request_id_of
from app.services import Upload, engine_info, extract, verify

router = APIRouter(prefix="/api/v1")


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _pool(request: Request) -> OcrPool:
    pool = cast(OcrPool, request.app.state.pool)
    if not pool.ready:
        raise HTTPException(status_code=503, detail="not_ready", headers={"Retry-After": "3"})
    return pool


async def _read_uploads(files: list[UploadFile], settings: Settings) -> list[Upload]:
    if not files:
        raise HTTPException(status_code=422, detail="At least one image is required.")
    if len(files) > settings.max_images_per_application:
        raise HTTPException(
            status_code=422, detail=f"At most {settings.max_images_per_application} images per application."
        )
    uploads: list[Upload] = []
    for f in files:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await f.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > settings.max_image_bytes:
                mb = settings.max_image_bytes // (1024 * 1024)
                raise ImageError(
                    "image_too_large",
                    f"'{f.filename}' is larger than the {mb} MB per-image limit.",
                    "Export the artwork at a smaller size or higher compression.",
                )
            chunks.append(chunk)
        if total == 0:
            raise ImageError("empty_file", f"'{f.filename}' is empty.", "Choose the image file again.")
        uploads.append(Upload(data=b"".join(chunks), filename=f.filename))
    return uploads


def _parse_application(raw: str) -> ApplicationFields:
    try:
        return ApplicationFields.model_validate(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="application must be a JSON object.") from exc
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"])
        raise HTTPException(status_code=422, detail=f"application.{loc}: {first['msg']}") from exc


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(request: Request) -> HealthResponse:
    pool = request.app.state.pool
    s = _settings(request)
    return HealthResponse(
        status="ok" if pool.ready else ("failed" if pool.error else "starting"),
        ready=pool.ready,
        error=pool.error,
        engine=engine_info(pool),
        max_concurrency=pool.workers,
        in_flight=pool.in_flight,
        requests_in_flight=request.app.state.limiter.in_flight,
        version=__version__,
        git_sha=s.git_sha,
    )


@router.get("/ready", tags=["system"], summary="Readiness probe: 200 once the OCR engines are warm, else 503")
async def ready(request: Request) -> dict[str, bool]:
    pool = request.app.state.pool
    if not pool.ready:
        detail = f"warm-up failed: {pool.error}" if pool.error else "not_ready"
        raise HTTPException(status_code=503, detail=detail, headers={"Retry-After": "3"})
    return {"ready": True}


@router.post(
    "/verify",
    response_model=VerifyResponse,
    tags=["verification"],
    summary="Verify one application against one or more label images",
)
async def verify_route(
    request: Request,
    application: str = Form(..., description="JSON object with the application fields"),
    images: list[UploadFile] = File(..., description="1 to 6 label images (front, back, neck...)"),
    settings: Settings = Depends(_settings),
) -> VerifyResponse:
    pool = _pool(request)
    app_fields = _parse_application(application)
    uploads = await _read_uploads(images, settings)
    interactive = request.headers.get("x-batch", "0") != "1"
    return await verify(app_fields, uploads, settings, pool, interactive=interactive, request_id=request_id_of(request))


@router.post(
    "/extract",
    response_model=ExtractResponse,
    tags=["verification"],
    summary="Read a label without application data (batch and extract-only mode)",
)
async def extract_route(
    request: Request,
    images: list[UploadFile] = File(...),
    settings: Settings = Depends(_settings),
) -> ExtractResponse:
    pool = _pool(request)
    uploads = await _read_uploads(images, settings)
    interactive = request.headers.get("x-batch", "0") != "1"
    return await extract(uploads, settings, pool, interactive=interactive, request_id=request_id_of(request))


@router.post(
    "/compare",
    response_model=CompareResponse,
    tags=["verification"],
    summary="Compare application data with previously extracted lines (no OCR, fast)",
)
async def compare_route(
    body: CompareRequest, request: Request, settings: Settings = Depends(_settings)
) -> CompareResponse:
    from app.pipeline.compare import compare

    if len(body.items) > settings.max_compare_items:
        raise HTTPException(status_code=422, detail=f"At most {settings.max_compare_items} items per compare call.")
    results = [
        CompareResponseItem(
            item_id=item.item_id, **compare(item.application, item.lines, item.images, settings).model_dump()
        )
        for item in body.items
    ]
    return CompareResponse(request_id=request_id_of(request), results=results)
