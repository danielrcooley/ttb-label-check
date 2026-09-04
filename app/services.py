"""Orchestration: bytes in, verified result out. The only module that touches both the OCR pool
and the pure pipeline."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field

import numpy as np

from app.config import Settings
from app.ocr.base import RawLine
from app.ocr.pool import OcrPool, Runner
from app.pipeline.compare import compare
from app.pipeline.extract import extract_fields
from app.pipeline.images import DecodedImage, decode_image, rotate_array, to_canonical
from app.pipeline.warning import WarningSpan, find_warning
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
    # Orientations the rotation retry read but did not keep (degrees -> lines in canonical
    # coordinates). The warning rescue looks there first; it costs nothing.
    alternates: dict[int, list[OcrLine]] = field(default_factory=dict)


# One extra read for the warning rescue: the image, its upload, and the turn in degrees (None =
# once more upright at bounded full resolution).
RescueRead = tuple[ProcessedImage, Upload, int | None]


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
    first read is poor (the one failure mode the engine does not recover on its own). The reads
    that lose the retry are kept as alternates rather than thrown away."""
    dec = decode_image(
        up.data, max_pixels=settings.max_image_pixels, max_side=settings.ocr_max_side, filename=up.filename
    )
    t0 = time.perf_counter()
    raw = await run(dec.array)
    h, w = dec.array.shape[:2]
    reads: dict[int, tuple[list[RawLine], int, int]] = {0: (raw, w, h)}
    chosen = 0
    mean = float(np.mean([r.confidence for r in raw])) if raw else 0.0
    if mean < settings.ocr_low_conf_retry or len(raw) < settings.ocr_min_lines_retry:
        for degrees in (90, 270):
            rot = rotate_array(dec.array, degrees)
            raw2 = await run(rot)
            reads[degrees] = (raw2, rot.shape[1], rot.shape[0])
            if _read_score(raw2) > _read_score(reads[chosen][0]) * 1.15:
                chosen = degrees
    ocr_ms = int((time.perf_counter() - t0) * 1000)
    raw_best, rw, rh = reads[chosen]
    lines = _to_lines(raw_best, dec, index, chosen, rw, rh)
    alternates = {d: _to_lines(r, dec, index, d, w2, h2) for d, (r, w2, h2) in reads.items() if d != chosen}
    info = ImageInfo(
        index=index,
        filename=up.filename,
        width=dec.width,
        height=dec.height,
        format=dec.format,
        rotated_degrees=chosen,
        quality=_quality(raw_best),
    )
    return ProcessedImage(info=info, lines=lines, queue_ms=queue_ms, ocr_ms=ocr_ms, alternates=alternates)


async def process_images(
    uploads: list[Upload], settings: Settings, pool: OcrPool, *, interactive: bool
) -> list[ProcessedImage]:
    """Interactive: each image takes its own slot so a front+back pair costs one image-time, and a
    statement that went unread gets one more round of reads (``_rescue_warning``).
    Batch: one slot is held for all the images of the request, so it can never be refused halfway,
    and every image is read exactly once. The batch screen reads images before it knows which
    application they belong to, so a front label, which carries no statement by design, must not
    trigger re-reads (measured: they cut batch throughput to a quarter, docs/LOADTEST.md)."""
    if interactive:

        async def one(i: int, u: Upload) -> ProcessedImage:
            async with pool.slot(interactive=True) as (run, queue_ms):
                return await process_image(u, i, settings, run, queue_ms=queue_ms)

        processed = list(await asyncio.gather(*(one(i, u) for i, u in enumerate(uploads))))
        if settings.warning_rescue:
            await _rescue_warning(uploads, processed, settings, pool)
        return processed
    async with pool.slot(interactive=False) as (run, queue_ms):
        return [await process_image(u, i, settings, run, queue_ms=queue_ms) for i, u in enumerate(uploads)]


async def _rescue_warning(
    uploads: list[Upload], processed: list[ProcessedImage], settings: Settings, pool: OcrPool
) -> None:
    """Two layouts hide the statement from the ordinary read: printed sideways along the edge of a
    small label that otherwise reads perfectly upright (so the low-confidence retry never fires),
    and printed in small type on large artwork (unreadable once the image is scaled to the working
    size). When no usable statement was found (none, or a span far from the required text): first
    look at the orientations the rotation retry already read, then run ONE round of extra reads in
    parallel on their own slots, at most one per worker: turned 270 then 90 degrees and, for large
    artwork, once more at bounded full resolution (that one first when the heading was seen but the
    body was not). One round keeps the interactive path inside its time budget whatever the number
    of workers, and the round is the same for the same input and configuration. The best span that
    beats the upright read is kept. A read that cannot get a slot is refused like any other
    interactive read (BusyError, HTTP 429), never skipped silently."""
    upright = find_warning([ln for p in processed for ln in p.lines])
    floor = upright.similarity if upright else 0.0
    if floor >= settings.warning_rescue_below:
        return
    for p in processed:  # free: what the retry read and did not keep
        for lines in p.alternates.values():
            span = find_warning(lines)
            if span is not None and span.similarity > floor:
                _adopt(p, span)
                floor = span.similarity
    if floor >= settings.warning_rescue_below:
        return
    plans: list[list[RescueRead]] = []
    for up, p in zip(uploads, processed, strict=True):
        if not p.info.quality.readable:
            continue  # nothing legible at all; turning it will not help
        seen = {p.info.rotated_degrees, *p.alternates}
        # 270 first: it unrolls a statement printed up a label's right edge, reading bottom to top,
        # which is how three of the four such labels in the real sample print it (docs/EVAL_REAL.md).
        turns: list[RescueRead] = [(p, up, d) for d in (270, 90) if d not in seen]
        side = min(settings.warning_rescue_max_side, max(p.info.width, p.info.height))
        full: list[RescueRead] = [(p, up, None)] if side > settings.ocr_max_side else []
        heading_seen = find_warning(p.lines) is not None
        plans.append(full + turns if heading_seen else turns + full)
    # The first read of every image before any second read, so a front+back pair shares the round.
    depth = max((len(plan) for plan in plans), default=0)
    ordered = [plan[k] for k in range(depth) for plan in plans if k < len(plan)]
    reads = ordered[: pool.workers]
    if not reads:
        return
    spans = await asyncio.gather(*(_rescue_read(p, up, degrees, settings, pool) for p, up, degrees in reads))
    best: dict[int, WarningSpan] = {}
    for (p, _, _), span in zip(reads, spans, strict=True):
        idx = p.info.index
        if span is not None and span.similarity > floor and (idx not in best or span.similarity > best[idx].similarity):
            best[idx] = span
    for p in processed:
        if p.info.index in best:
            _adopt(p, best[p.info.index])


def _adopt(p: ProcessedImage, span: WarningSpan) -> None:
    """Add a rescued statement to an image's lines and drop what the kept read had in the same
    places: the same strip of print read in another orientation is garbage, and two readings of
    one region must not both be there."""
    p.lines = [*(ln for ln in p.lines if not any(_same_place(ln, s) for s in span.lines)), *span.lines]


def _same_place(a: OcrLine, b: OcrLine) -> bool:
    """True when the boxes cover mostly the same area (more than half of the smaller one)."""
    ax = [pt[0] for pt in a.box]
    ay = [pt[1] for pt in a.box]
    bx = [pt[0] for pt in b.box]
    by = [pt[1] for pt in b.box]
    inter_w = max(0.0, min(max(ax), max(bx)) - max(min(ax), min(bx)))
    inter_h = max(0.0, min(max(ay), max(by)) - max(min(ay), min(by)))
    area_a = max(1.0, (max(ax) - min(ax)) * (max(ay) - min(ay)))
    area_b = max(1.0, (max(bx) - min(bx)) * (max(by) - min(by)))
    return inter_w * inter_h / min(area_a, area_b) > 0.5


async def _rescue_read(
    p: ProcessedImage, up: Upload, degrees: int | None, settings: Settings, pool: OcrPool
) -> WarningSpan | None:
    async with pool.slot(interactive=True) as (run, queue_ms):
        t0 = time.perf_counter()
        if degrees is None:
            side = min(settings.warning_rescue_max_side, max(p.info.width, p.info.height))
            dec = decode_image(up.data, max_pixels=settings.max_image_pixels, max_side=side, filename=up.filename)
            arr, turn = dec.array, 0
        else:
            dec = decode_image(
                up.data, max_pixels=settings.max_image_pixels, max_side=settings.ocr_max_side, filename=up.filename
            )
            arr, turn = rotate_array(dec.array, degrees), degrees
        raw = await run(arr)
        lines = _to_lines(raw, dec, p.info.index, turn, arr.shape[1], arr.shape[0])
        p.queue_ms += queue_ms
        p.ocr_ms += int((time.perf_counter() - t0) * 1000)
    return find_warning(lines)


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
