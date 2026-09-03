from __future__ import annotations

import pytest
from app.schemas import OcrLine


def make_line(
    text: str,
    *,
    y: float,
    x: float = 100,
    h: float = 40,
    w: float | None = None,
    image_index: int = 0,
    confidence: float = 0.98,
) -> OcrLine:
    """An OCR line with a rectangular box; width defaults to ~22 px per character."""
    w = w if w is not None else max(20.0, 22.0 * len(text))
    return OcrLine(
        image_index=image_index,
        text=text,
        confidence=confidence,
        box=((x, y), (x + w, y), (x + w, y + h), (x, y + h)),
    )


def make_lines(
    texts: list[str], *, start_y: float = 100, line_h: float = 40, gap: float = 12, image_index: int = 0
) -> list[OcrLine]:
    """Consecutive lines laid out top-to-bottom like a paragraph."""
    out = []
    y = start_y
    for t in texts:
        out.append(make_line(t, y=y, h=line_h, image_index=image_index))
        y += line_h + gap
    return out


@pytest.fixture
def lines_factory():
    return make_lines
