"""Alphabet-constrained CTC decoding.

The multilingual recognizer's dictionary has ~18,700 classes (Latin with diacritics, Cyrillic, CJK,
emoji). On English label artwork it occasionally emits an accented letter for a plain one
("alcoholi\u010d", "driv\u00e9"), which would turn an exact government warning into a "Needs review".
US alcohol labels are English text; the regulation text is pure ASCII. Restricting the decoder to
printable ASCII is therefore a recognizer configuration, applied to every line before the argmax,
not a normalization of the comparison: there is exactly one transcript, and "exact" still means the
transcript equals the required text character for character.

Consequence, stated in LIMITS.md: a genuinely accented letter on a label (a French back label, a
brand like "Ch\u00e2teau") is read as the best remaining class, usually its base letter, occasionally
the CTC blank (the character is dropped). Field comparisons already fold accents, and the evidence
crop shows the print as it is. The direction that matters legally: an accented character printed
inside the warning statement would be read as its base letter and could pass as exact. Confidence
values are renormalized over the allowed classes, so they remain probabilities.

The wrapper fails closed: an unexpected decoder class list or output shape raises instead of
silently decoding with the full alphabet.
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
    """Wraps rapidocr's CTCLabelDecode: masks disallowed classes, then delegates.

    Probabilities (softmax output, the PP-OCR export; every value in [0, 1]): disallowed classes are
    zeroed and each timestep is renormalized over the allowed classes, so the confidence the rest of
    the pipeline sees is P(class | allowed alphabet). Logits (any value outside [0, 1]): disallowed
    classes get -1e9. Either way the argmax picks the best allowed class. CTC blank (index 0) stays
    allowed, so padding timesteps still decode to nothing.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        chars = list(getattr(inner, "character", []))
        if not chars or chars[0] != "blank":
            raise RuntimeError("alphabet restriction: the decoder's class list must start with the CTC blank")
        self.character = chars
        self._suppress = ascii_mask(self.character)
        self.suppressed_classes = int(self._suppress.sum())

    def __call__(self, preds: np.ndarray, *args: Any, **kwargs: Any) -> Any:
        p = np.array(preds, copy=True)
        if p.ndim != 3 or p.shape[2] != self._suppress.shape[0]:
            raise RuntimeError(
                f"alphabet restriction: recognizer output has shape {p.shape}; "
                f"expected (batch, time, {self._suppress.shape[0]})"
            )
        if float(p.min()) >= 0.0 and float(p.max()) <= 1.0 + 1e-6:  # probabilities
            p[..., self._suppress] = 0.0
            total = p.sum(axis=2, keepdims=True)
            np.divide(p, total, out=p, where=total > 0)
        else:  # logits
            p[..., self._suppress] = -1e9
        return self._inner(p, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:  # everything else (decode, dict, ...) passes through
        return getattr(self._inner, name)
