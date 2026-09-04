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
from app.ocr.pool import BusyError, OcrPool, Runner
from app.pipeline.compare import compare
from app.pipeline.extract import extract_fields
from app.pipeline.images import DecodedImage, decode_image, rotate_array, to_canonical
from app.pipeline.warning import find_warning
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
    up: Upload, index: int, settings: Settings, run: Runner, *, queue_ms: int = 0
) -> ProcessedImage:
    """Decode one upload and read it on the given slot, retrying sideways orientations when the
    first read is poor (the one failure mode the engine does not recover on its own)."""
    dec = decode_image(
        up.data, max_pixels=settings.max_image_pixels, max_side=settings.ocr_max_side, filename=up.filename
    )
    t0 = time.perf_counter()
    raw = await run(dec.array)
    h, w = dec.array.shape[:2]
    best = (_read_score(raw), raw, 0, w, h)
    mean = float(np.mean([r.confidence for r in raw])) if raw else 0.0
    if mean < settings.ocr_low_conf_retry or len(raw) < settings.ocr_min_lines_retry:
        for degrees in (90, 270):
            rot = rotate_array(dec.array, degrees)
            raw2 = await run(rot)
            if _read_score(raw2) > best[0] * 1.15:
                best = (_read_score(raw2), raw2, degrees, rot.shape[1], rot.shape[0])
    ocr_ms = int((time.perf_counter() - t0) * 1000)
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
    return ProcessedImage(info=info, lines=lines, queue_ms=queue_ms, ocr_ms=ocr_ms)


async def process_images(
    uploads: list[Upload], settings: Settings, pool: OcrPool, *, interactive: bool
) -> list[ProcessedImage]:
    """Interactive: each image takes its own slot so a front+back pair costs one image-time.
    Batch: one slot is held for all the images of the request, so it can never be refused halfway."""
    if interactive:

        async def one(i: int, u: Upload) -> ProcessedImage:
            async with pool.slot(interactive=True) as (run, queue_ms):
                return await process_image(u, i, settings, run, queue_ms=queue_ms)

        processed = list(await asyncio.gather(*(one(i, u) for i, u in enumerate(uploads))))
    else:
        async with pool.slot(interactive=False) as (run, queue_ms):
            processed = [await process_image(u, i, settings, run, queue_ms=queue_ms) for i, u in enumerate(uploads)]
    if settings.warning_rescue:
        upright = find_warning([ln for p in processed for ln in p.lines])
        if upright is None or upright.similarity < settings.warning_rescue_below:
            await _rescue_sideways_warning(
                uploads,
                processed,
                settings,
                pool,
                interactive=interactive,
                floor=upright.similarity if upright else 0.0,
            )
    return processed


async def _rescue_sideways_warning(
    uploads: list[Upload],
    processed: list[ProcessedImage],
    settings: Settings,
    pool: OcrPool,
    *,
    interactive: bool,
    floor: float,
) -> None:
    """Two layouts hide the statement from the ordinary read: printed sideways along the edge of a
    small label that otherwise reads perfectly upright (so the low-confidence retry never fires),
    and printed in small type on large artwork (unreadable once the image is scaled to the working
    size). When no usable warning was found upright (none, or a span far from the required text),
    read each image rotated both ways, then once at bounded full resolution, and keep only the lines
    of a warning span that beats what the upright read had. Best effort: a request that cannot get a
    slot back keeps its result as it is."""
    try:
        async with pool.slot(interactive=interactive) as (run, _):
            for up, p in zip(uploads, processed, strict=True):
                if p.info.rotated_degrees or not p.info.quality.readable:
                    continue  # already read sideways, or nothing was legible at all
                dec = decode_image(
                    up.data, max_pixels=settings.max_image_pixels, max_side=settings.ocr_max_side, filename=up.filename
                )
                t0 = time.perf_counter()
                found = False
                for degrees in (90, 270):
                    rot = rotate_array(dec.array, degrees)
                    raw = await run(rot)
                    lines = _to_lines(raw, dec, p.info.index, degrees, rot.shape[1], rot.shape[0])
                    span = find_warning(lines)
                    if span is not None and span.similarity > floor:
                        p.lines.extend(span.lines)
                        floor = span.similarity
                        found = True
                        break
                # Large artwork with the statement in small type: unreadable at the working size,
                # legible once, at (bounded) full resolution.
                side = min(settings.warning_rescue_max_side, max(dec.width, dec.height))
                if not found and side > settings.ocr_max_side:
                    hi = decode_image(
                        up.data, max_pixels=settings.max_image_pixels, max_side=side, filename=up.filename
                    )
                    raw = await run(hi.array)
                    lines = _to_lines(raw, hi, p.info.index, 0, hi.array.shape[1], hi.array.shape[0])
                    span = find_warning(lines)
                    if span is not None and span.similarity > floor:
                        p.lines.extend(span.lines)
                        floor = span.similarity
                p.ocr_ms += int((time.perf_counter() - t0) * 1000)
    except BusyError:
        return


def engine_info(pool: OcrPool) -> EngineInfo:
    return EngineInfo(name="rapidocr-onnxruntime", models=pool.info(), workers=pool.workers)


def _timing(t0: float, processed: list[ProcessedImage]) -> Timing:
    return Timing(
        total_ms=int((time.perf_counter() - t0) * 1000),
        queue_ms=max((p.queue_ms for p in processed), default=0),
        ocr_ms=[p.ocr_ms for p in processed],
    )


async def verify(
    app: ApplicationFields,
    uploads: list[Upload],
    settings: Settings,
    pool: OcrPool,
    *,
    interactive: bool = True,
    request_id: str | None = None,
) -> VerifyResponse:
    t0 = time.perf_counter()
    processed = await process_images(uploads, settings, pool, interactive=interactive)
    lines = [ln for p in processed for ln in p.lines]
    images = [p.info for p in processed]
    result = compare(app, lines, images, settings)
    return VerifyResponse(
        request_id=request_id or new_request_id(),
        application=app,
        images=images,
        lines=lines,
        timing=_timing(t0, processed),
        engine=engine_info(pool),
        **result.model_dump(),
    )


async def extract(
    uploads: list[Upload],
    settings: Settings,
    pool: OcrPool,
    *,
    interactive: bool = False,
    request_id: str | None = None,
) -> ExtractResponse:
    t0 = time.perf_counter()
    processed = await process_images(uploads, settings, pool, interactive=interactive)
    lines = [ln for p in processed for ln in p.lines]
    return ExtractResponse(
        request_id=request_id or new_request_id(),
        images=[p.info for p in processed],
        lines=lines,
        fields=extract_fields(lines),
        timing=_timing(t0, processed),
        engine=engine_info(pool),
    )
