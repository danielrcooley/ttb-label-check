"""Fields the tool can read from a label without any application data (extract-only mode)."""

from __future__ import annotations

import re

from app.schemas import ExtractedFields, OcrLine

from .normalize import fold
from .parsers import parse_alcohol, parse_volumes
from .warning import find_warning

_ORIGIN = re.compile(
    r"(product of|produce of|imported by|imported from|made in|produced in|distilled in|bottled in|"
    r"country of origin)",
    re.I,
)
_BOTTLER = re.compile(
    r"\b(bottled by|distilled by|produced by|brewed by|vinted by|cellared by|imported by|"
    r"distilled and bottled|produced and bottled|brewed and bottled|vinted and bottled|packed by|blended by)\b",
    re.I,
)


def _height(ln: OcrLine) -> float:
    ys = [p[1] for p in ln.box]
    return max(ys) - min(ys)


def extract_fields(lines: list[OcrLine]) -> ExtractedFields:
    joined = " ".join(ln.text for ln in lines)
    alc = parse_alcohol(joined)
    volumes = parse_volumes(joined)
    origin = [ln.text for ln in lines if _ORIGIN.search(fold(ln.text))]
    bottler = [ln.text for ln in lines if _BOTTLER.search(fold(ln.text))]
    largest = max(lines, key=_height).text if lines else None
    return ExtractedFields(
        alcohol_percent=alc.percent if alc else None,
        proof=alc.proof if alc else None,
        net_contents_ml=sorted({v.ml for v in volumes}),
        warning_present=find_warning(lines) is not None,
        origin_lines=origin[:5],
        bottler_lines=bottler[:5],
        largest_text=largest,
    )
