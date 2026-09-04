import numpy as np
import pytest
from app.ocr.alphabet import AlphabetConstrainedDecode, ascii_mask


class FakeCtc:
    """Mimics rapidocr's CTCLabelDecode: argmax per timestep, collapse repeats, drop blank;
    confidence = mean of the winning class's value over the timesteps."""

    def __init__(self, character):
        self.character = character

    def __call__(self, preds, *a, **k):
        out = []
        for b, seq in enumerate(preds.argmax(axis=2)):
            text, prev = "", None
            for idx in seq:
                if idx != 0 and idx != prev:
                    text += self.character[idx]
                prev = idx
            out.append((text, float(preds[b].max(axis=1).mean())))
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


def test_probabilities_are_renormalized_over_the_allowed_classes():
    """The confidence the pipeline sees is P(class | allowed alphabet), not the raw runner-up value."""
    dec = AlphabetConstrainedDecode(FakeCtc(CHARS))
    preds = np.full((1, 1, len(CHARS)), 0.01)
    preds[0, 0, CHARS.index("č")] = 0.85
    preds[0, 0, CHARS.index("c")] = 0.06
    text, conf = dec(preds)[0][0]
    assert text == "c"
    allowed_total = 0.06 + 0.01 * (len(CHARS) - 2)
    assert conf == pytest.approx(0.06 / allowed_total)


def test_unexpected_decoder_output_fails_closed():
    dec = AlphabetConstrainedDecode(FakeCtc(CHARS))
    with pytest.raises(RuntimeError):
        dec(np.zeros((2, len(CHARS))))  # two dimensions: not (batch, time, class)
    with pytest.raises(RuntimeError):
        dec(np.zeros((1, 3, len(CHARS) + 1)))  # a different vocabulary size


def test_decoder_without_a_leading_blank_is_refused():
    with pytest.raises(RuntimeError):
        AlphabetConstrainedDecode(FakeCtc(["a", "blank", "c"]))
    with pytest.raises(RuntimeError):
        AlphabetConstrainedDecode(FakeCtc([]))
