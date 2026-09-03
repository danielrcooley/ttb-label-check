"""Government health warning statement checks (27 CFR Part 16).

Exactness is literal here: the only Pass is a character-for-character match (after collapsing
whitespace and unifying typographic quotes, which are rendering choices rather than wording).
Anything else is Needs review or a mismatch, never a Pass. The generic normalizer is not used.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.schemas import Evidence, OcrLine, Status, WarningReport

from .match import reading_order
from .normalize import collapse_ws, fold, join_hyphenated, unify_punctuation

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


def _anchor_score(text: str) -> int:
    return int(fuzz.partial_ratio(fold(ANCHOR), fold(text)))


def find_warning(lines: list[OcrLine]) -> WarningSpan | None:
    """Locate the warning statement: an anchor line, then following lines while similarity to the
    canonical text keeps improving. Returns the best span over all images."""
    best: WarningSpan | None = None
    best_sim = -1.0
    for group in reading_order(lines).values():
        for i, ln in enumerate(group):
            if _anchor_score(ln.text) < 80:
                continue
            m = _ANCHOR_RE.search(ln.text)
            anchor_text = m.group(0) if m else ln.text
            acc: list[OcrLine] = []
            local_best: tuple[float, list[OcrLine]] | None = None
            declines = 0
            for nxt in group[i:]:
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
                )
    return best


def _canon_form(s: str) -> str:
    return collapse_ws(unify_punctuation(s))


def word_diff(expected: str, found: str) -> str | None:
    """Compact word-level diff, e.g. '-may +can' or '-(2) '. None when identical."""
    a, b = _canon_form(expected).split(" "), _canon_form(found).split(" ")
    out: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if i2 > i1:
            out.append("-" + " ".join(a[i1:i2]))
        if j2 > j1:
            out.append("+" + " ".join(b[j1:j2]))
    return " | ".join(out) if out else None


def compare_warning(found: str) -> tuple[bool, bool, float]:
    """Returns (exact, case_only_difference, similarity 0-1)."""
    canon, got = _canon_form(CANONICAL), _canon_form(found)
    exact = canon == got
    case_only = (not exact) and canon.casefold() == got.casefold()
    similarity = fuzz.ratio(canon.casefold(), got.casefold()) / 100
    return exact, case_only, similarity


_PUNCT_ONLY = re.compile(r"^[^\w]+$")
_STRIP = re.compile(r"[^\w]")
_CONFUSABLE = str.maketrans({"0": "o", "1": "l", "5": "s", "8": "b", "2": "z", "6": "g", "|": "l", "!": "l"})


def _same_word_modulo_noise(a: str, b: str) -> bool:
    """True when two tokens differ only by punctuation, case, or OCR confusable characters."""
    ka = _STRIP.sub("", a).casefold().translate(_CONFUSABLE)
    kb = _STRIP.sub("", b).casefold().translate(_CONFUSABLE)
    if ka == kb:
        return True
    # a single dropped or inserted character inside a word of 5+ letters is OCR noise, not wording
    return len(ka) >= 5 and len(kb) >= 5 and fuzz.ratio(ka, kb) >= 85


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
            if _STRIP.sub("", "".join(left)).casefold() == _STRIP.sub("", "".join(right)).casefold():
                continue
            return "wording"
        # pure insert or delete: punctuation-only tokens are noise; anything with a letter or digit
        # (a word, or a clause number like "(2)") is a wording change
        tokens = left or right
        if all(_PUNCT_ONLY.match(t) for t in tokens):
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


def build_report(lines: list[OcrLine], *, review_similarity: float, mismatch_similarity: float) -> WarningReport:
    span = find_warning(lines)
    if span is None:
        return WarningReport(
            present=False,
            exact=False,
            similarity=0.0,
            found_text=None,
            diff=None,
            anchor_caps=Status.not_found,
            anchor_bold=Status.not_checked,
            body_not_bold=Status.not_checked,
            notes=[
                "No GOVERNMENT WARNING statement was found on any image. It is mandatory on all "
                "alcoholic beverages of 0.5% alcohol or more (27 CFR 16.21). If the warning is on a "
                "label image not uploaded, add that image."
            ],
        )
    exact, case_only, similarity = compare_warning(span.text)
    caps_status, caps_note = anchor_caps_status(span.anchor_text)
    kind = classify_difference(CANONICAL, span.text)
    notes: list[str] = []
    if exact:
        notes.append("Wording is exact (27 CFR 16.21).")
    elif case_only:
        notes.append("Wording matches except for letter case. Confirm the statement's capitalization on the image.")
    elif kind == "noise":
        notes.append(
            "Wording matches apart from punctuation or single characters as read, which is usually "
            "OCR noise (a dropped colon or comma). Compare the diff with the image."
        )
    else:
        notes.append(
            "Wording differs from the required text: a word is missing, added or changed. "
            "The statement must be word for word (27 CFR 16.21)."
        )
        # a wording change is a defect even when similarity is high; make the number reflect it
        similarity = min(similarity, mismatch_similarity - 0.01) if similarity >= review_similarity else similarity
    notes.append(caps_note)
    notes.append(
        "Bold type (anchor bold, remainder not bold) is not assessed automatically in this build; "
        "check it on the image (27 CFR 16.22(a)(2))."
    )
    return WarningReport(
        present=True,
        exact=exact,
        similarity=round(similarity, 4),
        found_text=span.text,
        diff=None if exact else word_diff(CANONICAL, span.text),
        anchor_caps=caps_status,
        anchor_bold=Status.not_checked,
        body_not_bold=Status.not_checked,
        evidence=[Evidence(image_index=ln.image_index, box=ln.box, text=ln.text) for ln in span.lines],
        notes=notes,
    )
