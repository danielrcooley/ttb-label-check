"""Type weight from pixels: is a line of print bold? (D-044, revised by D-045 after consult 008)

OCR gives text and boxes, not weight. What can be measured is the thickness of the ink strokes in
a line relative to the type height: bold faces run roughly 1.4 to 1.8 times heavier than their
regular weight, and a heading set in bold next to a body set regular shows as a clear step. The
measurement is a heuristic: it is reported as a ratio and the warning report decides, only a
confident reading becomes a finding, and small or low-contrast print is "not measured". It is
taken only on the lines of a located warning statement, which is where the regulation needs it.

Method per line:
1. The detector's quadrilateral is warped to an upright rectangle (``rectify``), so a rotated,
   skewed or vertical line measures like an upright one; the type height is the box's short edge.
2. Greyscale, Otsu threshold, the minority class is ink; the L2 distance transform over the ink
   averages about a quarter of the stroke width, so stroke = 4 x mean distance; the ratio divides
   by the unpadded type height. The estimator overstates strokes under about 3 px, evenly for a
   heading and its body, which is why strokes under MIN_STROKE are not measured.
3. A line that carries the heading is split into heading and remainder at a WORD GAP in the print
   (a run of empty columns) near where the heading's share of the characters says it ends; among
   the candidate gaps the one with the largest stroke drop across it wins, and when nothing drops
   (all one weight) the gap nearest the typographic estimate is used. Without a gap the boundary
   falls back to the character share, a weaker basis that the report never turns into a Match.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

# Tiny crops gain nothing from OpenCV's thread pool, and on a two-vCPU host that pool contends with the
# OCR engine's threads (one intra-op thread per worker). Keep OpenCV single-threaded in this process.
cv2.setNumThreads(1)

_ANCHOR = re.compile(r"g\s*o\s*v\s*e\s*r\s*n\s*m\s*e\s*n\s*t\s*w\s*a\s*r\s*n\s*i\s*n\s*g\s*:?", re.I)
# the second line of a heading set on two lines ("GOVERNMENT" / "WARNING: (1) ...")
_WARNING_START = re.compile(r"^\W{0,3}w\s*a\s*r\s*n\s*i\s*n\s*g\s*:?", re.I)
MIN_HEIGHT = 24  # px of type height: below this the strokes are a pixel or two and the ratio is noise
MIN_WIDTH = 24
MIN_STROKE = 3.8  # px: thinner strokes are quantized (a bold heading over a regular body measures 1.0 at 3 px)
MAX_RATIO = 0.6  # a "stroke" over half the type height is a solid block or a bar code, not print
PAD = 2  # px of the surrounding image kept around the rectified line
GAP_FRACTION = 0.12  # a word gap is at least this fraction of the type height wide
MARGIN_FRACTION = 0.15  # kept clear on each side of the split


@dataclass(frozen=True)
class LineWeight:
    weight: float | None  # whole line: stroke over type height
    head: float | None  # the heading's part of the line, when the line carries it
    tail: float | None  # the rest of that same line
    split: str | None = None  # how the boundary was found: "gap" (in the print) or "share" (of the characters)
    stroke_px: float | None = None  # whole line stroke width, pixels of the array measured
    type_px: float | None = None  # type height (the box's short edge), pixels of the array measured


def heading_match(text: str) -> re.Match[str] | None:
    """The heading in a line's text: 'GOVERNMENT WARNING:' anywhere, or 'WARNING:' opening the line."""
    return _ANCHOR.search(text) or _WARNING_START.match(text)


def to_gray(arr: np.ndarray) -> np.ndarray:
    """Greyscale once per read; the measurement accepts either the colour array or this."""
    return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY) if arr.ndim == 3 else arr


def rectify(arr: np.ndarray, box: Sequence[Sequence[float]] | np.ndarray) -> tuple[np.ndarray, float, float] | None:
    """The line's quadrilateral warped to an upright rectangle with the text running left to right
    and PAD pixels of the surrounding image on each side, plus the type height (mean short edge)
    and the length (mean long edge) in the array's own pixels. The detector gives four corners; for
    a vertical line the long edges are the sides, so the corners are re-ordered to start on a long
    edge, which turns the crop upright."""
    try:
        pts = np.array([[float(p[0]), float(p[1])] for p in box], dtype=np.float32)
    except (TypeError, ValueError):
        return None
    if pts.shape != (4, 2):
        return None
    edges = [float(np.linalg.norm(pts[(i + 1) % 4] - pts[i])) for i in range(4)]
    if edges[0] + edges[2] < edges[1] + edges[3]:
        pts = np.roll(pts, -1, axis=0)
        edges = edges[1:] + edges[:1]
    length = (edges[0] + edges[2]) / 2
    height = (edges[1] + edges[3]) / 2
    w, h = round(length), round(height)
    if w < 2 or h < 2:
        return None
    dst = np.array([[PAD, PAD], [PAD + w, PAD], [PAD + w, PAD + h], [PAD, PAD + h]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(pts, dst)
    crop: np.ndarray = cv2.warpPerspective(
        arr, m, (w + 2 * PAD, h + 2 * PAD), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )
    return crop, height, length


def _ink(gray: np.ndarray) -> np.ndarray | None:
    """Ink mask by Otsu (the minority class); None when the crop is blank, solid or mostly ink."""
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink: np.ndarray = np.asarray(bw) == 0
    if ink.mean() > 0.5:
        ink = ~ink  # light print on a dark ground
    frac = float(ink.mean())
    if frac < 0.03 or frac > 0.6:
        return None
    return ink


def stroke_px(gray: np.ndarray) -> float | None:
    """Stroke width in pixels of the print in a greyscale crop: four times the mean distance to the
    nearest non-ink pixel over the ink. None when the crop is too small or holds no clean ink."""
    if gray.ndim != 2:
        return None
    h, w = gray.shape
    if h < MIN_HEIGHT or w < MIN_WIDTH:
        return None
    ink = _ink(gray)
    if ink is None:
        return None
    dt = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 5)
    vals = dt[ink]
    if vals.size < 40:
        return None
    stroke = 4.0 * float(vals.mean())
    if stroke < MIN_STROKE:
        return None
    return stroke


def stroke_ratio(gray: np.ndarray, height: float | None = None) -> float | None:
    """Stroke width over the type height (the unpadded box height when given, else the crop's own);
    None when the crop is too small, holds no clean ink, or is a solid block rather than print."""
    s = stroke_px(gray)
    if s is None:
        return None
    ratio = s / float(height if height else gray.shape[0])
    if ratio > MAX_RATIO:
        return None
    return ratio


def _column_profile(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Per column: the stroke estimate over that column's ink (NaN without ink), and whether the
    column carries ink at all."""
    ink = _ink(gray)
    if ink is None:
        return None
    dt = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 5)
    counts = ink.sum(axis=0)
    sums = (dt * ink).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        prof = np.where(counts > 0, 4.0 * sums / np.maximum(counts, 1), np.nan)
    return prof, counts > 0


def _gaps(has_ink: np.ndarray, min_run: int, lo: int, hi: int) -> list[tuple[int, int]]:
    """Runs of at least min_run columns without ink whose start lies in [lo, hi)."""
    out: list[tuple[int, int]] = []
    n = has_ink.size
    c = 0
    while c < n:
        if has_ink[c]:
            c += 1
            continue
        start = c
        while c < n and not has_ink[c]:
            c += 1
        if c - start >= min_run and lo <= start < hi:
            out.append((start, c))
    return out


def _mean(prof: np.ndarray, a: int, b: int) -> float | None:
    part = prof[max(0, a) : max(0, b)]
    part = part[~np.isnan(part)]
    return float(part.mean()) if part.size >= 4 else None


def measure_line(arr: np.ndarray, box: Sequence[Sequence[float]] | np.ndarray, text: str) -> LineWeight:
    """Weights for one OCR line in the array it was read from. When the line carries the warning
    heading, the heading's part and the rest are measured apart (see the module docstring)."""
    rect = rectify(arr, box)
    if rect is None:
        return LineWeight(weight=None, head=None, tail=None)
    crop, height, length = rect
    if height < MIN_HEIGHT:  # the type itself, before padding: small print is not measured at all
        return LineWeight(weight=None, head=None, tail=None, type_px=height)
    gray = to_gray(crop)
    px = stroke_px(gray)
    weight = px / height if px is not None and px / height <= MAX_RATIO else None
    head = tail = split = None
    m = heading_match(text)
    if m and weight is not None and text.strip():
        share = m.end() / max(1, len(text))
        if m.end() >= len(text.strip()) - 2:  # the heading is the whole line
            head = weight
        else:
            x_share = PAD + length * share  # where the heading ends by its share of the characters
            margin = round(MARGIN_FRACTION * height)
            prof = _column_profile(gray)
            chosen: tuple[int, int] | None = None
            if prof is not None:
                col, has_ink = prof
                lo, hi = int(PAD + length * share * 0.9), int(PAD + length * min(1.0, share * 1.6))
                candidates = _gaps(has_ink, max(2, round(GAP_FRACTION * height)), lo, hi)
                best_drop = 0.0
                for g0, g1 in candidates:
                    left, right = _mean(col, PAD, g0 - margin), _mean(col, g1 + margin, PAD + int(length))
                    if left is None or right is None or right <= 0:
                        continue
                    if left / right > best_drop:
                        best_drop, chosen = left / right, (g0, g1)
                if chosen is None and candidates:  # one weight throughout: the typographic estimate
                    target = PAD + length * share * 1.25  # capitals set bold run about a quarter wider
                    chosen = min(candidates, key=lambda g: abs((g[0] + g[1]) / 2 - target))
            if chosen is not None:
                g0, g1 = chosen
                hc, tc = gray[:, : max(0, g0 - margin)], gray[:, g1 + margin :]
                split = "gap"
            else:
                hc, tc = gray[:, : int(x_share * 0.95)], gray[:, int(x_share * 1.08) :]
                split = "share"
            head = stroke_ratio(hc, height)
            tail = stroke_ratio(tc, height)
            if head is None or tail is None:
                split = None
    return LineWeight(weight=weight, head=head, tail=tail, split=split, stroke_px=px, type_px=height)
