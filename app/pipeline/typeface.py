"""Type weight from pixels: is a line of print bold?

OCR gives text and boxes, not weight. What can be measured is the thickness of the ink strokes in
a line's box relative to the type height: bold faces run roughly 1.4 to 1.8 times heavier than
their regular weight, and a heading set in bold next to a body set regular shows as a clear step.
The measurement is a heuristic: it is reported as a ratio and the warning report decides (D-044),
and only a confident reading becomes a finding; small or low-contrast print is "not measured".

Method per crop: greyscale, Otsu threshold, the minority class is ink; the distance transform over
the ink averages about a quarter of the stroke width, so stroke = 4 * mean distance; the result is
divided by the crop height (the type size, ascenders to descenders as the detector boxed it).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

# Tiny crops gain nothing from OpenCV's thread pool, and on a two-vCPU host that pool contends with the
# OCR engine's threads (one intra-op thread per worker). Keep OpenCV single-threaded in this process.
cv2.setNumThreads(1)

_ANCHOR = re.compile(r"g\s*o\s*v\s*e\s*r\s*n\s*m\s*e\s*n\s*t\s*w\s*a\s*r\s*n\s*i\s*n\s*g\s*:?", re.I)
MIN_HEIGHT = 24  # px of box height: below this the strokes are a pixel or two and the ratio is noise
MIN_WIDTH = 24
MIN_STROKE = 3.8  # px: thinner strokes are quantized (a bold heading over a regular body measures 1.0 at 3 px)


@dataclass(frozen=True)
class LineWeight:
    weight: float | None  # whole line
    head: float | None  # the "GOVERNMENT WARNING" part, when the line carries it
    tail: float | None  # the rest of that same line


def stroke_ratio(gray: np.ndarray) -> float | None:
    """Stroke width of the print in a greyscale crop, as a fraction of the crop height; None when
    the crop is too small or holds no clean ink."""
    if gray.ndim != 2:
        return None
    h, w = gray.shape
    if h < MIN_HEIGHT or w < MIN_WIDTH:
        return None
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = bw == 0
    if ink.mean() > 0.5:
        ink = ~ink  # light print on a dark ground
    frac = float(ink.mean())
    if frac < 0.03 or frac > 0.6:
        return None
    dt = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 5)
    vals = dt[ink]
    if vals.size < 40:
        return None
    stroke = 4.0 * float(vals.mean())  # overstates strokes under ~3 px, evenly for heading and body
    if stroke < MIN_STROKE:
        return None
    ratio = float(stroke / float(h))
    if ratio > 0.6:  # a "stroke" over half the type height is a solid block or a bar code, not print
        return None
    return ratio


def _crop(arr: np.ndarray, x0: float, y0: float, x1: float, y1: float, pad: int = 2) -> np.ndarray | None:
    h, w = arr.shape[:2]
    xa, ya = max(0, int(x0) - pad), max(0, int(y0) - pad)
    xb, yb = min(w, int(x1) + pad), min(h, int(y1) + pad)
    if xb - xa < MIN_WIDTH or yb - ya < MIN_HEIGHT:
        return None
    part = arr[ya:yb, xa:xb]
    return cv2.cvtColor(part, cv2.COLOR_RGB2GRAY) if part.ndim == 3 else part


def to_gray(arr: np.ndarray) -> np.ndarray:
    """Greyscale once per read; measure_line accepts either the colour array or this."""
    return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY) if arr.ndim == 3 else arr


def measure_line(arr: np.ndarray, box: object, text: str) -> LineWeight:
    """Weights for one OCR line in the array it was read from. When the line carries the warning
    heading, the heading's part and the rest are measured apart, splitting the box in proportion
    to the characters (a heading set heavier is a little wider than its share, so the head region
    is trimmed and the tail region starts a little later)."""
    pts = list(box)  # type: ignore[call-overload]
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if y1 - y0 < MIN_HEIGHT:  # the box itself, before padding: small print is not measured at all
        return LineWeight(weight=None, head=None, tail=None)
    whole = _crop(arr, x0, y0, x1, y1)
    weight = stroke_ratio(whole) if whole is not None else None
    head = tail = None
    m = _ANCHOR.search(text)
    if m and len(text.strip()) > 0:
        frac = m.end() / max(1, len(text))
        split = x0 + (x1 - x0) * frac
        if m.end() >= len(text.strip()) - 2:  # the heading is the whole line
            head = weight
        else:
            hc = _crop(arr, x0, y0, x0 + (split - x0) * 0.95, y1)
            tc = _crop(arr, x0 + (split - x0) * 1.08, y0, x1, y1)
            head = stroke_ratio(hc) if hc is not None else None
            tail = stroke_ratio(tc) if tc is not None else None
    return LineWeight(weight=weight, head=head, tail=tail)
