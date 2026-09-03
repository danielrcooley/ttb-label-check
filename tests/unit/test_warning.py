import textwrap

from app.pipeline.warning import (
    CANONICAL,
    build_report,
    classify_difference,
    find_warning,
    word_diff,
)
from app.schemas import Status

from tests.unit.conftest import make_lines

REVIEW, MISMATCH = 0.97, 0.80


def wrapped(text: str, width: int = 60) -> list[str]:
    return textwrap.wrap(text, width=width)


def report(lines):
    return build_report(lines, review_similarity=REVIEW, mismatch_similarity=MISMATCH)


def test_exact_warning_across_wrapped_lines_is_exact():
    lines = make_lines(["Product of USA", *wrapped(CANONICAL), "12345 67890"])
    r = report(lines)
    assert r.present and r.exact
    assert r.anchor_caps is Status.match
    assert r.diff is None
    assert len(r.evidence) == len(wrapped(CANONICAL))


def test_find_warning_stops_at_the_end_of_the_statement():
    lines = make_lines([*wrapped(CANONICAL), "Bottled by Old Tom Distillery, Bardstown, KY"])
    span = find_warning(lines)
    assert span is not None
    assert "Bottled by" not in span.text


def test_missing_warning_is_reported_as_absent():
    r = report(make_lines(["OLD TOM DISTILLERY", "Kentucky Straight Bourbon Whiskey", "750 mL"]))
    assert not r.present
    assert r.anchor_caps is Status.not_found
    assert "mandatory" in r.notes[0]


def test_title_case_anchor_is_flagged_for_review():
    text = CANONICAL.replace("GOVERNMENT WARNING:", "Government Warning:")
    r = report(make_lines(wrapped(text)))
    assert r.present and not r.exact
    assert r.anchor_caps is Status.needs_review
    assert "not all capitals" in r.notes[1] or "not all capitals" in " ".join(r.notes)


def test_one_word_substitution_is_a_wording_change_not_noise():
    text = CANONICAL.replace("may cause health problems", "can cause health problems")
    assert classify_difference(CANONICAL, text) == "wording"
    r = report(make_lines(wrapped(text)))
    assert r.present and not r.exact
    assert r.similarity < REVIEW  # verdict logic treats this as an issue, not a review item
    assert "-may" in r.diff and "+can" in r.diff


def test_missing_clause_number_is_a_wording_change():
    text = CANONICAL.replace("(2) Consumption", "Consumption")
    assert classify_difference(CANONICAL, text) == "wording"


def test_dropped_colon_or_comma_is_noise():
    assert classify_difference(CANONICAL, CANONICAL.replace("WARNING:", "WARNING")) == "noise"
    assert classify_difference(CANONICAL, CANONICAL.replace("General,", "General")) == "noise"
    r = report(make_lines(wrapped(CANONICAL.replace("WARNING:", "WARNING"))))
    assert r.present and not r.exact
    assert r.similarity >= REVIEW


def test_ocr_confusable_inside_a_word_is_noise():
    text = CANONICAL.replace("Surgeon", "Surge0n").replace("machinery", "machlnery")
    assert classify_difference(CANONICAL, text) == "noise"


def test_hyphenated_line_break_does_not_break_exactness():
    lines = make_lines(
        [
            "GOVERNMENT WARNING: (1) According to the Surgeon General,",
            "women should not drink alcoholic beverages during preg-",
            "nancy because of the risk of birth defects. (2) Consumption",
            "of alcoholic beverages impairs your ability to drive a car or",
            "operate machinery, and may cause health problems.",
        ]
    )
    assert report(lines).exact


def test_word_diff_is_compact():
    assert word_diff(CANONICAL, CANONICAL) is None
    d = word_diff("a b c", "a x c")
    assert d == "-b | +x"
