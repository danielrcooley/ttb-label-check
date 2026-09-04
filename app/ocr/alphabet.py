"""Alphabet-constrained CTC decoding.

The multilingual recognizer's dictionary has ~18,700 classes (Latin with diacritics, Cyrillic, CJK,
emoji). On English label artwork it occasionally emits an accented letter for a plain one
("alcoholi\u010d", "driv\u00e9"), which would turn an exact government warning into a "Needs review".
US alcohol labels are English text; the regulation text is pure ASCII. Restricting the decoder to
printable ASCII is therefore a recognizer configuration, applied to every line before the argmax,
not a normalization of the comparison: there is exactly one transcript, and "exact" still means the
transcript equals the required text character for character.

Consequence, stated in LIMITS.md: a genuinely accented letter on a label (a French back label, a
brand like "Ch\u00e2teau") is read as its base letter. Field comparisons already fold accents, and the
evidence crop shows the print as it is.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def ascii_mask(characters: list[str]) -> np.ndarray:
    """Boolean array, True for classes to suppress. Keeps blank (index 0), space, printable ASCII."""
    suppress = np.ones(len(characters), dtype=bool)
    for i, ch in enumerate(characters):
        if i == 0 or ch == "blank" or ch == " " or (len(ch) == 1 and 32 <= ord(ch) < 127):
            suppress[i] = False
    return suppress


class AlphabetConstrainedDecode:
    """Wraps rapidocr's CTCLabelDecode: zeroes disallowed classes, then delegates.

    Works on probabilities (softmax output, the PP-OCR export) and on logits (negative values):
    disallowed classes get 0 or -1e9 respectively, so the argmax picks the best allowed class.
    CTC blank stays allowed, so padding timesteps still decode to nothing.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.character = list(inner.character)
        self._suppress = ascii_mask(self.character)
        self.suppressed_classes = int(self._suppress.sum())

    def __call__(self, preds: np.ndarray, *args: Any, **kwargs: Any) -> Any:
        p = np.array(preds, copy=True)
        if p.ndim == 3 and p.shape[2] == self._suppress.shape[0]:
            fill = -1e9 if float(p.min()) < 0.0 else 0.0
            p[..., self._suppress] = fill
        return self._inner(p, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:  # everything else (decode, dict, ...) passes through
        return getattr(self._inner, name)
