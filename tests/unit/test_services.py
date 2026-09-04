"""Orchestration behaviours that need an engine but not a real one: the sideways-warning rescue."""

from __future__ import annotations

import asyncio
import textwrap
from io import BytesIO

import numpy as np
from app.config import Settings
from app.ocr.base import RawLine
from app.ocr.pool import OcrPool
from app.pipeline.warning import CANONICAL
from app.schemas import ApplicationFields
from app.services import Upload, verify
from PIL import Image

Box = tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]


def _box(x0: float, y0: float, x1: float, y1: float) -> Box:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class SidewaysWarningEngine:
    """Upright (landscape array): brand, class and net contents read perfectly, no warning.
    Rotated (portrait array): the warning statement, as a label that prints it vertically along one
    edge would present it once the image is turned."""

    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def recognize(self, rgb: np.ndarray) -> list[RawLine]:
        h, w = rgb.shape[:2]
        self.calls.append((w, h))
        if w >= h:
            return [
                RawLine("OLD TOM DISTILLERY", 0.99, _box(10, 10, 300, 50)),
                RawLine("Kentucky Straight Bourbon Whiskey", 0.99, _box(10, 60, 400, 90)),
                RawLine("45% Alc./Vol. (90 Proof) 750 mL", 0.99, _box(10, 100, 300, 130)),
            ]
        return [
            RawLine(text, 0.99, _box(10, 10 + 30 * i, 180, 34 + 30 * i))
            for i, text in enumerate(textwrap.wrap(CANONICAL, 60))
        ]

    def info(self) -> dict[str, str]:
        return {"engine": "fake"}


def _png(w: int = 400, h: int = 200) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "PNG")
    return buf.getvalue()


APP = ApplicationFields(
    beverage_type="spirits",
    brand_name="OLD TOM DISTILLERY",
    class_type="Kentucky Straight Bourbon Whiskey",
    alcohol_content="45% Alc./Vol. (90 Proof)",
    net_contents="750 mL",
)


def _run(settings: Settings) -> tuple[SidewaysWarningEngine, object]:
    engine = SidewaysWarningEngine()
    pool = OcrPool(settings, lambda: engine)
    pool.warmup()
    engine.calls.clear()
    res = asyncio.run(verify(APP, [Upload(data=_png(), filename="label.png")], settings, pool, interactive=True))
    pool.shutdown()
    return engine, res


def test_rescue_finds_a_warning_printed_sideways_and_maps_it_back():
    engine, res = _run(Settings(ocr_workers=1))
    assert res.warning.present and res.warning.exact, res.warning
    assert res.verdict == "ready_for_approval", res.summary
    assert engine.calls[0] == (400, 200) and any(w < h for w, h in engine.calls[1:])  # upright first, then rotated
    assert res.images[0].rotated_degrees == 0  # the upright read stayed the main read
    for ev in res.warning.evidence:  # mapped back into the upright image: tall narrow boxes inside it
        xs, ys = [p[0] for p in ev.box], [p[1] for p in ev.box]
        assert max(ys) - min(ys) > max(xs) - min(xs)
        assert min(xs) >= 0 and max(xs) <= 400 and min(ys) >= 0 and max(ys) <= 200
    assert next(c for c in res.checks if c.id == "brand_name").status == "match"


class TinyPrintEngine:
    """Large artwork: at the working size the statement is unreadable (only the brand reads);
    rotated it reads nothing; at full resolution the statement appears."""

    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def recognize(self, rgb: np.ndarray) -> list[RawLine]:
        h, w = rgb.shape[:2]
        self.calls.append((w, h))
        if w < h:
            return []
        if w <= 1280:
            return [
                RawLine("OLD TOM DISTILLERY", 0.99, _box(10, 10, 300, 50)),
                RawLine("Kentucky Straight Bourbon Whiskey", 0.99, _box(10, 60, 400, 90)),
                RawLine("45% Alc./Vol. (90 Proof) 750 mL", 0.99, _box(10, 100, 300, 130)),
            ]
        return [
            RawLine(text, 0.99, _box(1500, 10 + 30 * i, 2000, 34 + 30 * i))
            for i, text in enumerate(textwrap.wrap(CANONICAL, 60))
        ]

    def info(self) -> dict[str, str]:
        return {"engine": "fake"}


def test_rescue_reads_large_artwork_once_at_full_resolution():
    engine = TinyPrintEngine()
    settings = Settings(ocr_workers=1)
    pool = OcrPool(settings, lambda: engine)
    pool.warmup()
    engine.calls.clear()
    res = asyncio.run(
        verify(APP, [Upload(data=_png(3000, 1200), filename="big.png")], settings, pool, interactive=True)
    )
    pool.shutdown()
    assert res.warning.present and res.warning.exact, res.warning
    assert res.images[0].width == 3000 and res.images[0].height == 1200
    assert engine.calls[0] == (1280, 512) and engine.calls[-1] == (2048, 819)  # working size, then full resolution
    for ev in res.warning.evidence:  # boxes are in the original image's space
        xs, ys = [p[0] for p in ev.box], [p[1] for p in ev.box]
        assert min(xs) >= 2100 and max(xs) <= 3000 and min(ys) >= 0 and max(ys) <= 1200


def test_rescue_can_be_switched_off():
    engine, res = _run(Settings(ocr_workers=1, warning_rescue=False))
    assert not res.warning.present and res.warning.assessment == "absent"
    assert engine.calls == [(400, 200)]
