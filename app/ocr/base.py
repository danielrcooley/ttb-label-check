from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class RawLine:
    """One recognized text line in the coordinate space of the array that was passed in."""

    text: str
    confidence: float
    box: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]


class OcrEngine(Protocol):
    name: str

    def recognize(self, rgb: np.ndarray) -> list[RawLine]: ...

    def info(self) -> dict[str, str]: ...
