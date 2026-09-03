"""Find the label text that best corresponds to an application value.

Brand names and class/type designations wrap across lines on real labels, so candidates are
single lines and joins of up to three vertically adjacent lines on the same image.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.schemas import Evidence, OcrLine, Status

from .normalize import case_only_difference, collapse_ws, fold, key


@dataclass(frozen=True)
class Candidate:
    text: str
    score: int  # 0-100
    lines: tuple[OcrLine, ...]
    identical: bool  # same text after whitespace collapse
    fold_equal: bool  # equal after case/accents/quotes normalization
    key_equal: bool  # equal after dropping punctuation entirely

    @property
    def evidence(self) -> list[Evidence]:
        return [Evidence(image_index=ln.image_index, box=ln.box, text=ln.text) for ln in self.lines]


def _center_y(ln: OcrLine) -> float:
    return sum(p[1] for p in ln.box) / 4


def _height(ln: OcrLine) -> float:
    ys = [p[1] for p in ln.box]
    return max(ys) - min(ys)


def reading_order(lines: list[OcrLine]) -> dict[int, list[OcrLine]]:
    """Lines grouped by image, sorted top-to-bottom then left-to-right.

    Lines whose vertical centers fall within ~0.7 of the image's median line height are treated
    as one visual row and ordered by x; everything else is ordered by y. A common unit (the
    median height) is essential: dividing by each line's own height scrambles mixed-size text.
    """
    by_image: dict[int, list[OcrLine]] = {}
    for ln in lines:
        by_image.setdefault(ln.image_index, []).append(ln)
    for idx, group in by_image.items():
        med_h = statistics.median(_height(ln) for ln in group) or 1.0
        row_unit = max(0.7 * med_h, 1.0)
        by_image[idx] = sorted(group, key=lambda ln: (round(_center_y(ln) / row_unit), min(p[0] for p in ln.box)))
    return by_image


def _spans(lines: list[OcrLine], max_join: int) -> list[tuple[OcrLine, ...]]:
    """Single lines plus joins of up to max_join consecutive, vertically adjacent lines."""
    if not lines:
        return []
    med_h = statistics.median(_height(ln) for ln in lines) or 1.0
    spans: list[tuple[OcrLine, ...]] = []
    for i in range(len(lines)):
        spans.append((lines[i],))
        for j in range(i + 1, min(i + max_join, len(lines))):
            gap = _center_y(lines[j]) - _center_y(lines[j - 1])
            if gap > 2.5 * med_h or gap < 0:
                break
            spans.append(tuple(lines[i : j + 1]))
    return spans


def score_texts(expected: str, candidate: str) -> int:
    e, c = key(expected), key(candidate)
    if not e or not c:
        return 0
    full = fuzz.ratio(e, c)
    # When the candidate carries extra words (e.g. "... Aged 4 Years"), allow a substring match
    # but discount it slightly so an exact full-line match wins ties.
    partial = fuzz.partial_ratio(e, c) - 3 if len(c) > len(e) * 1.25 else 0
    return int(max(full, partial))


def best_span(expected: str, lines: list[OcrLine], *, max_join: int = 3) -> Candidate | None:
    best: Candidate | None = None
    for group in reading_order(lines).values():
        for span in _spans(group, max_join):
            text = collapse_ws(" ".join(ln.text for ln in span))
            sc = score_texts(expected, text)
            if best is None or sc > best.score or (sc == best.score and len(span) < len(best.lines)):
                best = Candidate(
                    text=text,
                    score=sc,
                    lines=span,
                    identical=collapse_ws(expected) == text,
                    fold_equal=fold(expected) == fold(text),
                    key_equal=key(expected) == key(text),
                )
    return best


def status_for(cand: Candidate | None, expected: str, *, review_at: int, mismatch_at: int) -> tuple[Status, str]:
    """Map a candidate to a status and a plain-language note."""
    if cand is None:
        return Status.not_found, "No text was read from the label images."
    if cand.identical:
        return Status.match, "Exact match."
    if cand.fold_equal:
        if case_only_difference(expected, cand.text):
            return Status.match, "Matches; only letter case differs on the label."
        return Status.match, "Matches; only accents, quote style or spacing differ on the label."
    if cand.key_equal:
        return Status.needs_review, "Same letters and digits; punctuation differs. Confirm on the image."
    if cand.score >= review_at:
        return Status.needs_review, "Close match. Could be OCR noise or a real difference; compare with the image."
    if cand.score >= mismatch_at:
        return Status.mismatch, "The closest text on the label differs from the application."
    return Status.not_found, "Nothing on the label resembles the application value."
