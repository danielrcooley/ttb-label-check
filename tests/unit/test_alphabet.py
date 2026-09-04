import numpy as np
from app.ocr.alphabet import AlphabetConstrainedDecode, ascii_mask


class FakeCtc:
    """Mimics rapidocr's CTCLabelDecode: argmax per timestep, collapse repeats, drop blank."""

    def __init__(self, character):
        self.character = character

    def __call__(self, preds, *a, **k):
        out = []
        for seq in preds.argmax(axis=2):
            text, prev = "", None
            for idx in seq:
                if idx != 0 and idx != prev:
                    text += self.character[idx]
                prev = idx
            out.append((text, 1.0))
        return out, []


CHARS = ["blank", "a", "\u010d", "c", "l", "o", "h", "i", " ", "1", "!"]


def test_mask_keeps_blank_space_ascii_and_suppresses_accents():
    m = ascii_mask(CHARS)
    assert not m[0] and not m[CHARS.index(" ")] and not m[CHARS.index("1")] and not m[CHARS.index("!")]
    assert m[CHARS.index("\u010d")] and not m[CHARS.index("c")]


def test_accented_winner_falls_back_to_best_ascii_class():
    inner = FakeCtc(CHARS)
    dec = AlphabetConstrainedDecode(inner)
    steps = 3
    preds = np.full((1, steps, len(CHARS)), 0.01)
    preds[0, 0, CHARS.index("a")] = 0.9
    preds[0, 1, CHARS.index("\u010d")] = 0.85  # accented letter wins unconstrained
    preds[0, 1, CHARS.index("c")] = 0.10  # plain letter is the best allowed class
    preds[0, 2, CHARS.index("h")] = 0.9
    assert inner(preds)[0][0][0] == "a\u010dh"
    assert dec(preds)[0][0][0] == "ach"


def test_logits_are_handled_and_blank_survives():
    inner = FakeCtc(CHARS)
    dec = AlphabetConstrainedDecode(inner)
    preds = np.full((1, 2, len(CHARS)), -5.0)
    preds[0, 0, CHARS.index("\u010d")] = 2.0  # only an accented class is confident
    preds[0, 0, 0] = 1.0  # blank is next: the timestep decodes to nothing rather than to junk
    preds[0, 1, CHARS.index("o")] = 3.0
    assert dec(preds)[0][0][0] == "o"


def test_passthrough_of_inner_attributes():
    dec = AlphabetConstrainedDecode(FakeCtc(CHARS))
    assert dec.character == CHARS and dec.suppressed_classes == 1
