from app.pipeline.match import best_span, score_texts, status_for
from app.schemas import Status

from tests.unit.conftest import make_line, make_lines

REVIEW, MISMATCH = 90, 70


def _status(expected, lines):
    cand = best_span(expected, lines)
    return status_for(cand, expected, review_at=REVIEW, mismatch_at=MISMATCH), cand


def test_exact_single_line_is_a_match():
    (st, note), cand = _status("OLD TOM DISTILLERY", make_lines(["EST. 1925", "OLD TOM DISTILLERY", "750 mL"]))
    assert st is Status.match and cand.identical
    assert note == "Exact match."


def test_case_only_difference_is_a_match_with_a_note():
    """Dave's example: 'STONE'S THROW' on the label, 'Stone's Throw' in the application."""
    (st, note), cand = _status("Stone's Throw", make_lines(["STONE'S THROW", "Straight Rye Whiskey"]))
    assert st is Status.match
    assert "letter case" in note
    assert cand.text == "STONE'S THROW"


def test_wrapped_class_type_is_joined_across_adjacent_lines():
    lines = make_lines(["OLD TOM DISTILLERY", "KENTUCKY STRAIGHT", "BOURBON WHISKEY", "45% Alc./Vol."])
    (st, _), cand = _status("Kentucky Straight Bourbon Whiskey", lines)
    assert st is Status.match
    assert len(cand.lines) == 2
    assert cand.text == "KENTUCKY STRAIGHT BOURBON WHISKEY"


def test_lines_far_apart_are_not_joined():
    top = make_line("KENTUCKY STRAIGHT", y=100)
    far = make_line("BOURBON WHISKEY", y=900)
    (st, _), cand = _status("Kentucky Straight Bourbon Whiskey", [top, far])
    assert len(cand.lines) == 1
    assert st is not Status.match


def test_ocr_confusable_inside_a_word_is_needs_review():
    (st, _), cand = _status("OLD TOM DISTILLERY", make_lines(["OLD T0M DISTILLERY"]))
    assert st is Status.needs_review
    assert cand.score >= REVIEW


def test_missing_apostrophe_is_needs_review_not_match():
    (st, note), _ = _status("Stone's Throw", make_lines(["STONES THROW"]))
    assert st is Status.needs_review
    assert "punctuation" in note


def test_unrelated_text_is_not_found():
    (st, _), _ = _status("OLD TOM DISTILLERY", make_lines(["Crafted in small batches", "Product of USA"]))
    assert st is Status.not_found


def test_candidate_with_extra_words_scores_as_close_match():
    (st, _), cand = _status(
        "Kentucky Straight Bourbon Whiskey", make_lines(["Kentucky Straight Bourbon Whiskey Aged 4 Years"])
    )
    assert st is Status.needs_review
    assert cand.score >= REVIEW


def test_score_prefers_full_match_over_partial():
    assert score_texts("Vodka", "Vodka") == 100
    assert score_texts("Vodka", "Premium Vodka Distilled Five Times") < 100


def test_empty_lines_gives_not_found():
    (st, _), cand = _status("OLD TOM DISTILLERY", [])
    assert st is Status.not_found and cand is None


def test_reading_order_uses_vertical_overlap_not_height_buckets():
    from app.pipeline.match import reading_order

    big = make_line("OLD TOM", y=100, h=120)  # huge brand line
    small1 = make_line("KENTUCKY STRAIGHT", y=240, h=30)
    small2 = make_line("BOURBON WHISKEY", y=276, h=30)  # tight spacing
    right = make_line("EST. 1991", y=245, h=30, x=900)  # same row as small1, to the right
    order = reading_order([small2, right, big, small1])[0]
    assert [ln.text for ln in order] == ["OLD TOM", "KENTUCKY STRAIGHT", "EST. 1991", "BOURBON WHISKEY"]
