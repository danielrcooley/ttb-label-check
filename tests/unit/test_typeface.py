"""Type weight from pixels: stroke width over height, on drawn strokes of known width."""

from __future__ import annotations

import numpy as np
from app.pipeline.typeface import MIN_HEIGHT, measure_line, stroke_ratio


def _strokes(width: int, height: int = 48, count: int = 8, canvas_w: int = 320, ink: int = 0) -> np.ndarray:
    """A white canvas with `count` vertical bars of the given stroke width, like a line of print."""
    arr = np.full((height, canvas_w, 3), 255, dtype=np.uint8)
    step = canvas_w // (count + 1)
    for i in range(1, count + 1):
        x = i * step
        arr[6 : height - 6, x : x + width] = ink
    return arr


def _gray(arr: np.ndarray) -> np.ndarray:
    return arr[:, :, 0]


def test_bold_strokes_measure_heavier_than_regular_in_proportion():
    regular = stroke_ratio(_gray(_strokes(4)))
    bold = stroke_ratio(_gray(_strokes(7)))
    assert regular is not None and bold is not None
    assert 1.35 < bold / regular < 2.1  # 7 px over 4 px; the estimator overstates thin strokes a little
    assert 0.08 < regular < 0.14 and 0.14 < bold < 0.22


def test_too_small_or_empty_crops_are_not_measured():
    assert stroke_ratio(_gray(_strokes(4, height=MIN_HEIGHT - 4))) is None
    assert stroke_ratio(np.full((48, 320), 255, dtype=np.uint8)) is None  # blank
    assert stroke_ratio(_gray(_strokes(1, height=48))) is None  # hairline strokes are noise


def test_light_print_on_a_dark_ground_measures_the_same():
    dark = _strokes(6)
    inverted = 255 - dark
    a, b = stroke_ratio(_gray(dark)), stroke_ratio(_gray(inverted))
    assert a is not None and b is not None and abs(a - b) < 0.01


def test_heading_line_is_split_into_heading_and_remainder():
    # a line whose left 40% carries heavy strokes (the heading) and whose right part is regular
    canvas = np.full((48, 600, 3), 255, dtype=np.uint8)
    canvas[:, :240] = _strokes(7, canvas_w=240, count=6)
    canvas[:, 260:] = _strokes(4, canvas_w=340, count=8)
    text = "GOVERNMENT WARNING: (1) According to the Surgeon General,"  # the heading is ~19 of 57 characters
    box = ((0, 0), (600, 0), (600, 48), (0, 48))
    lw = measure_line(canvas, box, text)
    assert lw.weight is not None and lw.head is not None and lw.tail is not None
    assert lw.head > lw.tail * 1.3
    plain = measure_line(canvas, box, "because of the risk of birth defects")
    assert plain.head is None and plain.tail is None and plain.weight is not None


def test_solid_blocks_and_bar_codes_are_not_print():
    """A crop that is mostly ink, or whose 'strokes' are wider than half the height (a bar code or a
    filled panel the detector boxed as a line), must not yield a weight; one of these crashed the
    real-label evaluation with a ratio of 2.2 before the cap."""
    assert stroke_ratio(np.zeros((48, 320), dtype=np.uint8)) is None
    assert stroke_ratio(_gray(_strokes(60, count=2))) is None
