"""Orchestration behaviours that need an engine but not a real one: the warning rescue (one extra
round of reads, interactive only) and what the rotation retry leaves behind for it."""

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


def _front_lines() -> list[RawLine]:
    return [
        RawLine("OLD TOM DISTILLERY", 0.99, _box(10, 10, 300, 50)),
        RawLine("Kentucky Straight Bourbon Whiskey", 0.99, _box(10, 60, 400, 90)),
        RawLine("45% Alc./Vol. (90 Proof) 750 mL", 0.99, _box(10, 100, 300, 130)),
    ]


def _statement_lines(text: str = CANONICAL, x0: float = 10, x1: float = 180) -> list[RawLine]:
    return [RawLine(t, 0.99, _box(x0, 10 + 30 * i, x1, 34 + 30 * i)) for i, t in enumerate(textwrap.wrap(text, 60))]


def _turn(rgb: np.ndarray) -> int:
    """Which way a landscape test image was turned, from the marker pixel painted at its top-left
    corner: numpy's 90-degree turn puts it bottom-left, the 270-degree turn top-right."""
    h, w = rgb.shape[:2]
    if w >= h:
        return 0
    return 90 if rgb[-1, 0].sum() == 0 else 270


class SidewaysWarningEngine:
    """Upright (landscape array): brand, class and net contents read perfectly, no warning.
    Turned (portrait array): the warning statement, as a label that prints it vertically along one
    edge would present it once the image is turned. Turned 270 (the first turn the round tries) it
    reads with one word wrong, turned 90 it reads exactly."""

    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def recognize(self, rgb: np.ndarray) -> list[RawLine]:
        h, w = rgb.shape[:2]
        self.calls.append((w, h))
        turn = _turn(rgb)
        if turn == 0:
            return _front_lines()
        if turn == 270:
            return _statement_lines(CANONICAL.replace("may cause", "can cause"))
        return _statement_lines()

    def info(self) -> dict[str, str]:
        return {"engine": "fake"}


def _png(w: int = 400, h: int = 200) -> bytes:
    im = Image.new("RGB", (w, h), "white")
    im.putpixel((0, 0), (0, 0, 0))  # orientation marker, see _turn
    buf = BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


APP = ApplicationFields(
    beverage_type="spirits",
    brand_name="OLD TOM DISTILLERY",
    class_type="Kentucky Straight Bourbon Whiskey",
    alcohol_content="45% Alc./Vol. (90 Proof)",
    net_contents="750 mL",
)


def _run(settings: Settings, engine=None, *, interactive: bool = True, png: bytes | None = None):
    engine = engine or SidewaysWarningEngine()
    pool = OcrPool(settings, lambda: engine)
    pool.warmup()
    engine.calls.clear()
    res = asyncio.run(
        verify(APP, [Upload(data=png or _png(), filename="label.png")], settings, pool, interactive=interactive)
    )
    pool.shutdown()
    return engine, res


def test_rescue_finds_a_warning_printed_sideways_and_maps_it_back():
    engine, res = _run(Settings(ocr_workers=1))
    assert res.warning.present, res.warning
    assert engine.calls[0] == (400, 200) and engine.calls[1:] == [(200, 400)]  # upright, then ONE turned read
    assert res.images[0].rotated_degrees == 0  # the upright read stayed the main read
    for ev in res.warning.evidence:  # mapped back into the upright image: tall narrow boxes inside it
        xs, ys = [p[0] for p in ev.box], [p[1] for p in ev.box]
        assert max(ys) - min(ys) > max(xs) - min(xs)
        assert min(xs) >= 0 and max(xs) <= 400 and min(ys) >= 0 and max(ys) <= 200
    assert next(c for c in res.checks if c.id == "brand_name").status == "match"


def test_rescue_is_one_round_across_the_workers_and_keeps_the_best_read():
    """With two workers both turns run in the same round; the exact read wins over the one with a
    wrong word (review 005, item 1.4). With one worker only the first turn (270) runs, the round
    being the budget, and the verdict is whatever that read gave."""
    engine, res = _run(Settings(ocr_workers=2))
    assert len(engine.calls) == 3 and engine.calls[0] == (400, 200)
    assert res.warning.present and res.warning.exact, res.warning
    assert res.verdict == "ready_for_approval", res.summary
    engine, res = _run(Settings(ocr_workers=1))
    assert len(engine.calls) == 2
    assert res.warning.present and res.warning.assessment == "wording", res.warning


def test_batch_requests_read_every_image_exactly_once():
    """The batch screen reads images before it knows their application; a front label carries no
    statement by design and must not pay for re-reads (review 005, section 3)."""
    engine, res = _run(Settings(ocr_workers=2), interactive=False)
    assert engine.calls == [(400, 200)]
    assert not res.warning.present and res.warning.assessment == "absent"


class PoorUprightEngine:
    """A sideways photo: upright reads two low-confidence lines (so the general rotation retry
    fires); turned 90 the page is full of confident text but no statement; turned 270 it holds the
    statement and little else. The retry keeps the 90 read (more text); the rescue must take the
    statement from the 270 read it already has, without another engine call."""

    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def recognize(self, rgb: np.ndarray) -> list[RawLine]:
        h, w = rgb.shape[:2]
        self.calls.append((w, h))
        turn = _turn(rgb)
        if turn == 0:
            return [RawLine("~~~", 0.5, _box(10, 10, 60, 30)), RawLine("~~", 0.5, _box(10, 40, 60, 60))]
        if turn == 90:
            return [RawLine(f"LINE {i}", 0.99, _box(10, 10 + 30 * i, 180, 34 + 30 * i)) for i in range(12)]
        return _statement_lines()

    def info(self) -> dict[str, str]:
        return {"engine": "fake"}


def test_rotation_retry_reads_are_reused_before_any_rescue_read():
    engine, res = _run(Settings(ocr_workers=1), PoorUprightEngine())
    assert engine.calls == [(400, 200), (200, 400), (200, 400)]  # upright, 90, 270: nothing more
    assert res.images[0].rotated_degrees == 90
    assert res.warning.present and res.warning.exact, res.warning


class TinyPrintEngine:
    """Large artwork: at the working size the heading reads but the statement's body is unreadable
    (only the brand reads); turned it reads nothing; at full resolution the statement appears."""

    name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def recognize(self, rgb: np.ndarray) -> list[RawLine]:
        h, w = rgb.shape[:2]
        self.calls.append((w, h))
        if w < h:
            return []
        if w <= 1280:
            return [*_front_lines(), RawLine("GOVERNMENT WARNING: ~ ~~ ~", 0.9, _box(700, 10, 900, 20))]
        return _statement_lines(x0=1500, x1=2000)

    def info(self) -> dict[str, str]:
        return {"engine": "fake"}


def test_rescue_reads_large_artwork_once_at_full_resolution():
    """The heading was seen but the body was not: the full-resolution read goes first in the plan,
    so it is the one read a single worker gets."""
    engine, res = _run(Settings(ocr_workers=1), TinyPrintEngine(), png=_png(3000, 1200))
    assert res.warning.present and res.warning.exact, res.warning
    assert res.images[0].width == 3000 and res.images[0].height == 1200
    assert engine.calls == [(1280, 512), (2048, 819)]  # working size, then full resolution, nothing else
    for ev in res.warning.evidence:  # boxes are in the original image's space
        xs, ys = [p[0] for p in ev.box], [p[1] for p in ev.box]
        assert min(xs) >= 2100 and max(xs) <= 3000 and min(ys) >= 0 and max(ys) <= 1200


def test_rescue_can_be_switched_off():
    engine, res = _run(Settings(ocr_workers=1, warning_rescue=False))
    assert not res.warning.present and res.warning.assessment == "absent"
    assert engine.calls == [(400, 200)]
