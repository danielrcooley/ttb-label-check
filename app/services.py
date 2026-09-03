"""Orchestration: bytes in, verified result out. The only module that touches both the OCR pool
and the pure pipeline."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass

import numpy as np

from app.config import Settings
from app.ocr.base import RawLine
from app.ocr.pool import OcrPool
from app.pipeline.compare import compare
from app.pipeline.extract import extract_fields
from app.pipeline.images import DecodedImage, decode_image, rotate_array, to_canonical
from app.schemas import (
    ApplicationFields,
    EngineInfo,
    ExtractResponse,
    ImageInfo,
    ImageQuality,
    OcrLine,
    Timing,
    VerifyResponse,
)


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Upload:
    data: bytes
    filename: str | None


@dataclass
class ProcessedImage:
    info: ImageInfo
    lines: list[OcrLine]
    queue_ms: int
    ocr_ms: int


def _to_lines(raw: list[RawLine], dec: DecodedImage, index: int, degrees: int, rot_w: int, rot_h: int) -> list[OcrLine]:
    return [
        OcrLine(
            image_index=index,
            text=r.text,
            confidence=round(r.confidence, 4),
            box=to_canonical(r.box, scale=dec.scale, degrees=degrees, rot_w=rot_w, rot_h=rot_h),
        )
        for r in raw
    ]


def _read_score(raw: list[RawLine]) -> float:
    """How much confident text was read: sum of confidences of lines at or above 0.5."""
    return float(sum(r.confidence for r in raw if r.confidence >= 0.5))


def _quality(raw: list[RawLine]) -> ImageQuality:
    if not raw:
        return ImageQuality(
            mean_confidence=0.0,
            line_count=0,
            readable=False,
            reason="No text was detected. The image may be blank, too small, or not a label.",
        )
    mean = float(np.mean([r.confidence for r in raw]))
    if mean < 0.6:
        return ImageQuality(
            mean_confidence=round(mean, 3),
            line_count=len(raw),
            readable=False,
            reason="Text was detected but read with low confidence. The image may be blurry, "
            "low contrast, or photographed at an angle. Request a clearer image.",
        )
    return ImageQuality(mean_confidence=round(mean, 3), line_count=len(raw), readable=True)


async def process_image(
    up: Upload, index: int, settings: Settings, pool: OcrPool, *, interactive: bool
) -> ProcessedImage:
    dec = decode_image(
        up.data, max_pixels=settings.max_image_pixels, max_side=settings.ocr_max_side, filename=up.filename
    )
    raw, q_ms, o_ms = await pool.recognize(dec.array, interactive=interactive)
    h, w = dec.array.shape[:2]
    best = (_read_score(raw), raw, 0, w, h)
    mean = float(np.mean([r.confidence for r in raw])) if raw else 0.0
    if mean < settings.ocr_low_conf_retry or len(raw) < settings.ocr_min_lines_retry:
        # Sideways photos are the one failure mode the engine does not recover on its own.
        for degrees in (90, 270):
            rot = rotate_array(dec.array, degrees)
            raw2, q2, o2 = await pool.recognize(rot, interactive=interactive)
            q_ms += q2
            o_ms += o2
            if _read_score(raw2) > best[0] * 1.15:
                best = (_read_score(raw2), raw2, degrees, rot.shape[1], rot.shape[0])
    _, raw_best, degrees, rw, rh = best
    lines = _to_lines(raw_best, dec, index, degrees, rw, rh)
    info = ImageInfo(
        index=index,
        filename=up.filename,
        width=dec.width,
        height=dec.height,
        format=dec.format,
        rotated_degrees=degrees,
        quality=_quality(raw_best),
    )
    return ProcessedImage(info=info, lines=lines, queue_ms=q_ms, ocr_ms=o_ms)


async def process_images(
    uploads: list[Upload], settings: Settings, pool: OcrPool, *, interactive: bool
) -> list[ProcessedImage]:
    # Images of one application fan out across workers so a front+back pair costs one image-time.
    return list(
        await asyncio.gather(
            *(process_image(u, i, settings, pool, interactive=interactive) for i, u in enumerate(uploads))
        )
    )


def engine_info(pool: OcrPool) -> EngineInfo:
    return EngineInfo(name="rapidocr-onnxruntime", models=pool.info(), workers=pool.workers)


async def verify(
    app: ApplicationFields, uploads: list[Upload], settings: Settings, pool: OcrPool, *, interactive: bool = True
) -> VerifyResponse:
    t0 = time.perf_counter()
    processed = await process_images(uploads, settings, pool, interactive=interactive)
    lines = [ln for p in processed for ln in p.lines]
    images = [p.info for p in processed]
    result = compare(app, lines, images, settings)
    timing = Timing(
        total_ms=int((time.perf_counter() - t0) * 1000),
        queue_ms=max((p.queue_ms for p in processed), default=0),
        ocr_ms=[p.ocr_ms for p in processed],
    )
    return VerifyResponse(
        request_id=new_request_id(),
        application=app,
        images=images,
        lines=lines,
        timing=timing,
        engine=engine_info(pool),
        **result.model_dump(),
    )


async def extract(
    uploads: list[Upload], settings: Settings, pool: OcrPool, *, interactive: bool = False
) -> ExtractResponse:
    t0 = time.perf_counter()
    processed = await process_images(uploads, settings, pool, interactive=interactive)
    lines = [ln for p in processed for ln in p.lines]
    timing = Timing(
        total_ms=int((time.perf_counter() - t0) * 1000),
        queue_ms=max((p.queue_ms for p in processed), default=0),
        ocr_ms=[p.ocr_ms for p in processed],
    )
    return ExtractResponse(
        request_id=new_request_id(),
        images=[p.info for p in processed],
        lines=lines,
        fields=extract_fields(lines),
        timing=timing,
        engine=engine_info(pool),
    )
