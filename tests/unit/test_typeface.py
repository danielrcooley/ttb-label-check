"""Type weight from pixels: stroke width over type height, on drawn strokes of known width and on
text set in a real proportional face when one is installed (D-044 / D-045)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from app.pipeline.typeface import MIN_HEIGHT, PAD, measure_line, rectify, stroke_ratio

HEADING = "GOVERNMENT WARNING:"
BODY = " (1) According to the Surgeon General, women should"


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


def _box(w: int, h: int, x0: int = 0, y0: int = 0):
    return ((x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h))


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


def test_the_denominator_is_the_type_height_not_the_padded_crop():
    """Review 007: the crop keeps two pixels of surroundings on each side; the ratio still divides
    by the box's own height."""
    crop = _gray(_strokes(6, height=48 + 2 * PAD))
    assert stroke_ratio(crop, height=48) == pytest.approx(stroke_ratio(crop) * (48 + 2 * PAD) / 48)


def test_heading_line_is_split_at_the_word_gap_between_heavy_and_regular_strokes():
    # a line whose left 40% carries heavy strokes (the heading) and whose right part is regular
    canvas = np.full((48, 600, 3), 255, dtype=np.uint8)
    canvas[:, :240] = _strokes(7, canvas_w=240, count=6)
    canvas[:, 260:] = _strokes(4, canvas_w=340, count=8)
    text = HEADING + BODY  # the heading is 19 of 70 characters, less than its share of the width
    lw = measure_line(canvas, _box(600, 48), text)
    assert lw.weight is not None and lw.head is not None and lw.tail is not None
    assert lw.split == "gap" and lw.head > lw.tail * 1.3
    assert lw.stroke_px is not None and lw.type_px == 48
    plain = measure_line(canvas, _box(600, 48), "because of the risk of birth defects")
    assert plain.head is None and plain.tail is None and plain.weight is not None


def test_a_line_of_one_weight_splits_near_the_typographic_estimate_and_measures_equal():
    canvas = _strokes(6, canvas_w=600, count=16)
    lw = measure_line(canvas, _box(600, 48), HEADING + BODY)
    assert lw.split == "gap" and lw.head is not None and lw.tail is not None
    assert 0.9 < lw.head / lw.tail < 1.1


def test_rotated_and_vertical_lines_measure_like_the_upright_one():
    """The detector's quadrilateral is rectified, so a line read from a rotated array, or boxed
    vertically in an upright read, gives the same stroke and type height (review 007, 1.1)."""
    canvas = np.full((120, 700, 3), 255, dtype=np.uint8)
    canvas[36:84, 50:650] = _strokes(6, canvas_w=600, count=16)
    up = measure_line(canvas, _box(600, 48, 50, 36), HEADING + BODY)
    turned = np.rot90(canvas)  # counter-clockwise: (x, y) -> (y, W - x)
    width = canvas.shape[1]
    box = tuple((y, width - x) for x, y in _box(600, 48, 50, 36))
    side = measure_line(turned, box, HEADING + BODY)
    assert up.weight is not None and side.weight is not None
    assert abs(side.weight - up.weight) / up.weight < 0.08
    assert side.type_px == pytest.approx(up.type_px, abs=1) and side.head is not None and side.tail is not None


def test_solid_blocks_and_bar_codes_are_not_print():
    """A crop that is mostly ink, or whose 'strokes' are wider than half the height (a bar code or a
    filled panel the detector boxed as a line), must not yield a weight; one of these crashed the
    real-label evaluation with a ratio of 2.2 before the cap."""
    assert stroke_ratio(np.zeros((48, 320), dtype=np.uint8)) is None
    assert stroke_ratio(_gray(_strokes(60, count=2))) is None
    assert rectify(np.zeros((10, 10, 3), dtype=np.uint8), ((0, 0), (1, 0), (1, 1), (0, 1))) is None


# ----------------------------------------------------------------------------- a real face
_FONTS = [
    (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
    (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ),
]


def _faces():
    for regular, bold in _FONTS:
        if regular.exists() and bold.exists():
            return regular, bold
    return None


def _set(heading_face: Path, body_face: Path, size: int = 40) -> tuple[np.ndarray, tuple]:
    """The heading and the body set on one line in the given faces; returns the array and the box."""
    from PIL import Image, ImageDraw, ImageFont

    hf, bf = ImageFont.truetype(str(heading_face), size), ImageFont.truetype(str(body_face), size)
    img = Image.new("RGB", (1500, size * 2), "white")
    d = ImageDraw.Draw(img)
    x = 20
    d.text((x, size // 2), HEADING, font=hf, fill="black")
    x += int(d.textlength(HEADING, font=hf))
    d.text((x, size // 2), BODY, font=bf, fill="black")
    x += int(d.textlength(BODY, font=bf))
    arr = np.asarray(img)
    ink = np.where((arr < 128).any(axis=2))
    y0, y1 = int(ink[0].min()) - 2, int(ink[0].max()) + 3
    return arr, _box(x + 6 - 14, y1 - y0, 14, y0)


@pytest.mark.skipif(_faces() is None, reason="no sans face installed to set text with")
def test_bold_heading_over_regular_body_in_a_real_face_is_split_at_the_gap_and_reads_heavier():
    regular, bold = _faces()
    arr, box = _set(bold, regular)
    lw = measure_line(arr, box, HEADING + BODY)
    assert lw.split == "gap" and lw.head is not None and lw.tail is not None, lw
    assert lw.head / lw.tail >= 1.20, lw
    all_bold = measure_line(*(_set(bold, bold)), HEADING + BODY)
    assert all_bold.head is not None and all_bold.tail is not None and all_bold.head / all_bold.tail <= 1.08, all_bold
    all_regular = measure_line(*(_set(regular, regular)), HEADING + BODY)
    assert all_regular.head is not None and all_regular.tail is not None
    assert all_regular.head / all_regular.tail <= 1.08, all_regular


@pytest.mark.skipif(_faces() is None, reason="no sans face installed to set text with")
def test_ocr_text_with_dropped_or_added_characters_still_splits_at_the_same_gap():
    regular, bold = _faces()
    arr, box = _set(bold, regular)
    exact = measure_line(arr, box, HEADING + BODY)
    noisy = measure_line(arr, box, "GOVERNMENTWARNING: (1)Acording to the Surgeon General, women should")
    assert noisy.split == "gap" and exact.head is not None and noisy.head is not None
    assert abs(noisy.head / noisy.tail - exact.head / exact.tail) < 0.05
