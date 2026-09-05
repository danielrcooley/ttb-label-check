"""Government health warning statement checks (27 CFR Part 16).

Exactness is literal here: the only Pass is a character-for-character match of every word and
punctuation mark, ignoring letter case, the style of quotation marks, and spacing next to
punctuation ("WARNING :(1)"). Those are rendering choices rather than wording: 16.22 requires
capitals only for the two anchor words, and approved labels commonly print the remainder in
capitals (docs/EVAL_REAL.md). A word boundary that moves between letters ("womens hould") is not
spacing; it changes the words and can never be exact. The anchor's capitals are checked
separately. Anything else is Needs review or a mismatch, never a Pass. The generic fuzzy
normalizer is not used.
"""

from __future__ import annotations

import difflib
import re
import statistics
import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz
from rapidfuzz.distance import OSA

from app.schemas import Evidence, OcrLine, Status, WarningReport

from .match import reading_order
from .normalize import collapse_ws, fold, join_hyphenated, unify_punctuation
from .typeface import heading_match

# Verbatim text of 27 CFR 16.21, verified against the eCFR API on 2026-09-03 (docs/REGULATIONS.md).
CANONICAL = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic "
    "beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic "
    "beverages impairs your ability to drive a car or operate machinery, and may cause health problems."
)
ANCHOR = "GOVERNMENT WARNING"
_ANCHOR_RE = re.compile(r"g\s*o\s*v\s*e\s*r\s*n\s*m\s*e\s*n\s*t\s*w\s*a\s*r\s*n\s*i\s*n\s*g", re.I)
_CANON_FOLD = fold(CANONICAL)


@dataclass(frozen=True)
class WarningSpan:
    text: str
    lines: tuple[OcrLine, ...]
    anchor_text: str  # the anchor as OCR read it, for the caps check
    similarity: float = 0.0  # to the canonical text, 0-1, case-folded


def _anchor_score(text: str) -> int:
    """Both words must be present (fuzzily); \"WARNING\" alone is not an anchor."""
    t = fold(text)
    return int(min(fuzz.partial_ratio("government", t), fuzz.partial_ratio("warning", t)))


def _anchor_at(group: list[OcrLine], i: int) -> tuple[str, list[OcrLine]] | None:
    """The anchor as read and the lines that form it, or None. Either both words on one line, or
    "GOVERNMENT" alone on this line with a line starting "WARNING" a little further down the same
    column (a common layout when the two words are set large; the reading order may slip an
    unrelated neighbour between them, which is left out of the statement)."""
    ln = group[i]
    if _anchor_score(ln.text) >= 80:
        m = _ANCHOR_RE.search(ln.text)
        return (m.group(0) if m else ln.text), [ln]
    if fuzz.ratio("government", fold(ln.text)) >= 85:
        for j in range(i + 1, min(i + 4, len(group))):
            if fold(group[j].text).startswith("warning") and _column_overlap(ln, group[j]) >= 0.3:
                return ln.text + " " + group[j].text, [ln, group[j]]
    return None


def _extent(ln: OcrLine) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in ln.box], [p[1] for p in ln.box]
    return min(xs), max(xs), min(ys), max(ys)


def _column_overlap(a: OcrLine, b: OcrLine) -> float:
    """Overlap across the reading direction, as a fraction of the narrower line. Boxes live in the
    oriented original image, so a statement read from a rotated image (a sideways photo, or a label
    that prints the warning vertically along its edge) comes back as vertical strips stacked left to
    right: for those, the column is shared along y, not x. A vertical strip and a horizontal line
    are never one column, whatever their boxes overlap: the strips of a statement printed along
    the edge of an upright label cross the label's other text without belonging to it."""
    ax0, ax1, ay0, ay1 = _extent(a)
    bx0, bx1, by0, by1 = _extent(b)
    a_vertical, b_vertical = (ay1 - ay0) > (ax1 - ax0), (by1 - by0) > (bx1 - bx0)
    if a_vertical != b_vertical:
        return 0.0
    if a_vertical:
        inter = max(0.0, min(ay1, by1) - max(ay0, by0))
        return inter / max(1.0, min(ay1 - ay0, by1 - by0))
    inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    return inter / max(1.0, min(ax1 - ax0, bx1 - bx0))


def find_warning(lines: list[OcrLine]) -> WarningSpan | None:
    """Locate the warning statement: an anchor line, then following lines while similarity to the
    canonical text keeps improving. Returns the best span over all images."""
    best: WarningSpan | None = None
    best_sim = -1.0
    # Both directions: a statement printed vertically maps back with its lines running right to left
    # or left to right depending on which way the label was turned, and the anchor may sit last.
    ordered = [g for grp in reading_order(lines).values() for g in (grp, grp[::-1])]
    for group in ordered:
        for i, ln in enumerate(group):
            anchor = _anchor_at(group, i)
            if anchor is None:
                continue
            anchor_text, head = anchor
            acc: list[OcrLine] = list(head)
            local_best: tuple[float, list[OcrLine]] | None = (
                fuzz.ratio(_CANON_FOLD, fold(join_hyphenated([x.text for x in acc]))) / 100,
                list(acc),
            )
            declines = 0
            start = next(k for k, x in enumerate(group) if x is head[-1])  # identity, not equality
            for nxt in group[start + 1 :]:
                if _column_overlap(ln, nxt) < 0.3:
                    continue  # a different column or an unrelated block
                acc.append(nxt)
                sim = fuzz.ratio(_CANON_FOLD, fold(join_hyphenated([x.text for x in acc]))) / 100
                if local_best is None or sim > local_best[0]:
                    local_best = (sim, list(acc))
                    declines = 0
                else:
                    declines += 1
                    if declines >= 2:
                        break
                if "health problems" in fold(nxt.text) and len(acc) > 1:
                    break
            if local_best and local_best[0] > best_sim:
                best_sim = local_best[0]
                best = WarningSpan(
                    text=join_hyphenated([x.text for x in local_best[1]]),
                    lines=tuple(local_best[1]),
                    anchor_text=anchor_text,
                    similarity=local_best[0],
                )
    return best


def _canon_form(s: str) -> str:
    # Whitespace and typographic quotes are rendering, not wording; everything else must be literal.
    return collapse_ws(unify_punctuation(s))


def word_diff(expected: str, found: str) -> str | None:
    """Compact word-level diff, e.g. '-may +can' or '-(2) '. None when identical. Words are aligned
    ignoring letter case (a statement printed in capitals shows only its real differences)."""
    a, b = _canon_form(expected).split(" "), _canon_form(found).split(" ")
    out: list[str] = []
    matcher = difflib.SequenceMatcher(a=[w.casefold() for w in a], b=[w.casefold() for w in b], autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if i2 > i1:
            out.append("-" + " ".join(a[i1:i2]))
        if j2 > j1:
            out.append("+" + " ".join(b[j1:j2]))
    return " | ".join(out) if out else None


_TOKEN = re.compile(r"[a-z0-9]+|[^a-z0-9\s]")


def _tokens(s: str) -> list[str]:
    """What exactness compares: the words (runs of letters and digits) and the punctuation marks,
    in order, ignoring letter case and the spacing between them. "WARNING :(1)" and "WARNING: (1)"
    give the same tokens; "womens hould" and "women should" do not."""
    return _TOKEN.findall(_canon_form(s).casefold())


def compare_warning(found: str) -> tuple[bool, float]:
    """Returns (exact, similarity 0-1). Exact ignores letter case and spacing around punctuation,
    nothing else."""
    canon, got = _canon_form(CANONICAL), _canon_form(found)
    exact = _tokens(canon) == _tokens(got)
    similarity = fuzz.ratio(canon.casefold(), got.casefold()) / 100
    return exact, similarity


_PUNCT_ONLY = re.compile(r"^[^\w]+$")
_NUMBER_ONLY = re.compile(r"^\W*\d+\W*$")
_STRIP = re.compile(r"[^\w]")
_TRAILING_DIGITS = re.compile(r"[\d\W_]+$")
# OCR confusables folded to one canonical letter: 0/o, 1/l/i/|/!, 5/s, 8/b, 2/z, 6/g
_CONFUSABLE = str.maketrans({"0": "o", "1": "l", "i": "l", "|": "l", "!": "l", "5": "s", "8": "b", "2": "z", "6": "g"})


def _canon_word(w: str) -> str:
    decomposed = unicodedata.normalize("NFKD", w)
    letters = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _STRIP.sub("", letters).casefold().translate(_CONFUSABLE)


def _same_word_modulo_noise(a: str, b: str) -> bool:
    """True when two tokens differ only by punctuation, case, accents, OCR confusables, or one slip
    (a character dropped, added, changed, or two adjacent ones swapped) in a word of four or more
    letters. A slip is left to the person with the diff (Needs review): approved labels read as
    "Suregon" and "YOURS" were small print, and one that reads "WOMAN" genuinely prints it
    (docs/EVAL_REAL.md); the tool cannot tell the two apart from an image, so it never passes either.
    A whole word replaced, added or dropped is a wording change."""
    ka, kb = _canon_word(a), _canon_word(b)
    if ka == kb:
        return True
    return len(ka) >= 4 and len(kb) >= 4 and OSA.distance(ka, kb) <= 1


def classify_difference(expected: str, found: str) -> str:
    """'exact' | 'noise' (punctuation, case, confusables) | 'wording' (a word added, dropped or replaced)."""
    a = _canon_form(expected).split(" ")
    b = _canon_form(found).split(" ")
    if a == b:
        return "exact"
    verdict = "noise"
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        a=[w.casefold() for w in a], b=[w.casefold() for w in b], autojunk=False
    ).get_opcodes():
        if tag == "equal":
            continue
        left, right = a[i1:i2], b[j1:j2]
        if tag == "replace" and len(left) == len(right):
            if all(_same_word_modulo_noise(x, y) for x, y in zip(left, right, strict=True)):
                continue
            return "wording"
        if tag == "replace":
            # e.g. "Surgeon General," read as "SurgeonGeneral," (merged) or split words
            if _canon_word("".join(left)) == _canon_word("".join(right)):
                continue
            # a number swept in from a barcode or lot code printed against the statement, glued to
            # the word it landed on: 'or' read as 'OR88 186"223932'
            if (
                len(left) == 1
                and right
                and _same_word_modulo_noise(left[0], _TRAILING_DIGITS.sub("", right[0]))
                and all(_STRIP.sub("", t).isdigit() for t in right[1:])
            ):
                continue
            return "wording"
        # pure insert or delete: punctuation-only tokens are noise; a bare number swept in from a
        # neighbouring line (a lot code, a year) is noise; anything else added or dropped (a word, a
        # missing clause number like "(2)") is a wording change
        tokens = left or right
        if all(_PUNCT_ONLY.match(t) for t in tokens):
            continue
        if tag == "insert" and all(_NUMBER_ONLY.match(t) for t in tokens):
            continue
        return "wording"
    return verdict


def anchor_caps_status(anchor_text: str) -> tuple[Status, str]:
    letters = [c for c in anchor_text if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return Status.match, "GOVERNMENT WARNING appears in capital letters."
    return (
        Status.needs_review,
        f"Read as '{collapse_ws(anchor_text)}', which is not all capitals. "
        "Capital letters are required (27 CFR 16.22(a)(2)). Confirm on the image.",
    )


@dataclass(frozen=True)
class TypeWeight:
    ratio: float | None  # heading stroke over body stroke, when comparable
    basis: str  # what was compared, or why nothing was
    split: str | None = None  # "gap" or "share" for a same-line comparison, "alone" for a standalone heading


SIZE_TOLERANCE = 0.10  # a standalone heading is compared only when its type height is within this of the body's


def type_weight_ratio(span: WarningSpan) -> TypeWeight:
    """Heading stroke weight over body stroke weight, and what it was measured against. The sound
    comparison is the heading against the rest of its own line: same size, same face, same box, so
    the normalization cancels. When the heading stands alone on its line, its stroke thickness in
    pixels (canonical, so reads at different scales compare) is set against the median of the other
    lines', but only when the type heights agree within SIZE_TOLERANCE: a larger size has thicker
    strokes at the same weight (consult 008). No ratio when the print was too small or faint."""
    heading = next((ln for ln in span.lines if heading_match(ln.text)), None)
    if heading is None:
        return TypeWeight(None, "no heading line")
    if heading.weight_head is None:
        return TypeWeight(None, "too small")
    if heading.weight_tail:
        return TypeWeight(heading.weight_head / heading.weight_tail, "the rest of its line", heading.weight_split)
    others = [ln for ln in span.lines if ln is not heading and ln.stroke_px and ln.type_px]
    if len(others) < 2 or not heading.stroke_px or not heading.type_px:
        return TypeWeight(None, "too small", "alone")
    body_type = statistics.median(ln.type_px for ln in others if ln.type_px)
    if body_type <= 0 or abs(heading.type_px / body_type - 1.0) > SIZE_TOLERANCE:
        return TypeWeight(None, "size differs", "alone")
    body_px = statistics.median(ln.stroke_px for ln in others if ln.stroke_px)
    return TypeWeight(heading.stroke_px / body_px if body_px else None, "the other lines", "alone")


def type_weight_status(
    span: WarningSpan, *, heading_min_ratio: float, same_max_ratio: float
) -> tuple[Status, str, str, TypeWeight]:
    """Bold type from the stroke weights measured on the pixels (app/pipeline/typeface.py): the
    heading must be in bold type (27 CFR 16.22(a)(2)). A heading clearly heavier than the rest of
    the statement is a Match. Anything the measurement cannot confirm is Needs review with the
    reason, so the agent confirms it on the image (D-047): the same weight (either the heading is
    not bold or the whole statement is), a small difference, a boundary found only by counting
    characters, print too small or too faint, or a heading set in a different size. Never a
    failure: it measures print, not wording. Returns (status, reading, note, measurement); the
    reading is one of heavier, same, inconclusive, boundary_uncertain, not_measured."""
    tw = type_weight_ratio(span)
    rule = "(27 CFR 16.22(a)(2))"
    confirm = f"Confirm on the image that GOVERNMENT WARNING is in bold type {rule}."
    if tw.ratio is None:
        reason = {
            "too small": "the print is too small or too faint at the working size",
            "no heading line": "GOVERNMENT WARNING was not read as its own words",
            "size differs": (
                "GOVERNMENT WARNING is set in a different size from the statement, and a larger size has thicker "
                "strokes at the same weight"
            ),
        }.get(tw.basis, tw.basis)
        return (Status.needs_review, "not_measured", f"Bold type could not be measured: {reason}. {confirm}", tw)
    if tw.ratio <= same_max_ratio:
        return (
            Status.needs_review,
            "same",
            f"GOVERNMENT WARNING and {tw.basis} measure the same weight, so it does not stand out as bold type. "
            f"{confirm}",
            tw,
        )
    if tw.ratio >= heading_min_ratio and tw.split == "share":
        return (
            Status.needs_review,
            "boundary_uncertain",
            "GOVERNMENT WARNING measures heavier than the rest of its line, but the boundary between them could not be "
            f"found in the print, so it is not counted. {confirm}",
            TypeWeight(tw.ratio, "boundary uncertain", tw.split),
        )
    if tw.ratio >= heading_min_ratio:
        return (
            Status.match,
            "heavier",
            f"GOVERNMENT WARNING is set about {tw.ratio:.1f} times heavier than {tw.basis}: bold type {rule}.",
            tw,
        )
    return (
        Status.needs_review,
        "inconclusive",
        f"Bold type could not be judged with confidence from this image: GOVERNMENT WARNING measures only slightly "
        f"heavier than {tw.basis}. {confirm}",
        tw,
    )


def build_report(
    lines: list[OcrLine],
    *,
    mismatch_similarity: float,
    heading_min_ratio: float = 1.20,
    same_max_ratio: float = 1.05,
) -> WarningReport:
    """Assess the warning statement. ``assessment`` drives the verdict:
    exact -> pass; noise -> Needs review; wording/absent -> issue. The anchor's capitals and the
    type weight are separate format checks (``anchor_caps``, ``anchor_bold``)
    that can send an exact statement to Needs review, never to an issue."""
    span = find_warning(lines)
    if span is None:
        return WarningReport(
            present=False,
            exact=False,
            assessment="absent",
            similarity=0.0,
            found_text=None,
            diff=None,
            anchor_caps=Status.not_found,
            anchor_bold=Status.not_checked,
            notes=[
                "No GOVERNMENT WARNING statement was found on any image. It is mandatory on all alcoholic "
                "beverages of 0.5% alcohol or more (27 CFR 16.21). If the warning is on a label image not "
                "uploaded, add that image. A statement printed sideways in very small type can also go "
                "unread; check the image."
            ],
        )
    exact, similarity = compare_warning(span.text)
    caps_status, caps_note = anchor_caps_status(span.anchor_text)
    bold_status, bold_reading, bold_note, tw = type_weight_status(
        span, heading_min_ratio=heading_min_ratio, same_max_ratio=same_max_ratio
    )
    if exact:
        assessment = "exact"
    else:
        assessment = classify_difference(CANONICAL, span.text)
        if assessment == "noise" and similarity < mismatch_similarity:
            assessment = "wording"  # too many differences to call it noise
    notes = {
        "exact": "Wording is exact (27 CFR 16.21).",
        "noise": (
            "Wording matches apart from punctuation, an accent, or single characters as read, which is usually "
            "OCR noise (a dropped colon, a '1' read as 'i', a stray accent). Compare the diff with the image."
        ),
        "wording": (
            "Wording differs from the required text: a word is missing, added or changed. "
            "The statement must be word for word (27 CFR 16.21)."
        ),
    }
    return WarningReport(
        present=True,
        exact=exact,
        assessment=assessment,
        similarity=round(similarity, 4),
        found_text=span.text,
        diff=None if exact else word_diff(CANONICAL, span.text),
        anchor_caps=caps_status,
        anchor_bold=bold_status,
        type_weight_reading=bold_reading,
        type_weight_ratio=round(tw.ratio, 3) if tw.ratio is not None else None,
        type_weight_basis=tw.basis + (f" ({tw.split})" if tw.split in ("gap", "share") else ""),
        evidence=[Evidence(image_index=ln.image_index, box=ln.box, text=ln.text) for ln in span.lines],
        notes=[notes[assessment], caps_note, bold_note],
    )
