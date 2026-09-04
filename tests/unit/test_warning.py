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

MISMATCH = 0.80


def wrapped(text: str, width: int = 60) -> list[str]:
    return textwrap.wrap(text, width=width)


def report(lines):
    return build_report(lines, mismatch_similarity=MISMATCH)


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
    assert r.present and r.exact  # the wording is exact; the format check is what fails
    assert r.anchor_caps is Status.needs_review
    assert "not all capitals" in r.notes[1] or "not all capitals" in " ".join(r.notes)


def test_warning_read_from_a_rotated_image_accumulates_its_vertical_lines():
    """A sideways photo, or a label that prints the statement vertically along its edge, is read
    from a rotated array; mapped back, its lines are vertical strips stacked left to right. The
    column filter must follow the text direction or the span stops after the anchor."""
    from app.schemas import OcrLine

    lines = []
    for i, text in enumerate(wrapped(CANONICAL)):
        x = 1800 + 40 * i  # each line is a tall narrow box; consecutive lines step right
        lines.append(
            OcrLine(image_index=0, text=text, confidence=0.99, box=((x, 170), (x + 36, 170), (x + 36, 1300), (x, 1300)))
        )
    r = report(lines)
    assert r.present and r.exact, (r.assessment, r.similarity, r.diff)


def test_anchor_split_over_two_lines_is_found():
    """Seen on real labels: "GOVERNMENT" and "WARNING:" set large on two lines, the statement below."""
    head = "GOVERNMENT WARNING: "
    lines = make_lines(["Distilled and Bottled by", "GOVERNMENT", "WARNING:", *wrapped(CANONICAL[len(head) :], 40)])
    r = report(lines)
    assert r.present and r.exact, (r.assessment, r.similarity, r.diff)
    assert r.anchor_caps is Status.match
    # the reading order can slip an unrelated neighbour between the two words; it must be left out
    lines = make_lines(["GOVERNMENT", "LLC Lebanon IN", "WARNING:", *wrapped(CANONICAL[len(head) :], 40)])
    r = report(lines)
    assert r.present and r.exact, (r.assessment, r.similarity, r.diff)


def test_tight_column_lines_keep_top_to_bottom_order():
    """Seen on real labels: a narrow column of small type whose OCR boxes overlap vertically, with a
    few pixels of jitter on the left edge. Two lines must not swap places (that turned an exact
    statement into "wording" with the same words deleted and re-inserted)."""
    from tests.unit.conftest import make_line

    texts = wrapped(CANONICAL, 24)
    lines = [make_line(t, y=100 + i * 28, x=1393 + (i % 2) * 3, h=60) for i, t in enumerate(texts)]
    r = report(lines)
    assert r.exact, r.diff


def test_body_printed_in_capitals_is_exact():
    """16.22 requires capitals only for the anchor; approved labels commonly print the remainder in
    capitals too (docs/EVAL_REAL.md). Letter case is typography, not wording."""
    head = "GOVERNMENT WARNING: "
    text = head + CANONICAL[len(head) :].upper()
    r = report(make_lines(wrapped(text)))
    assert r.exact and r.assessment == "exact" and r.diff is None
    assert r.anchor_caps is Status.match


def test_spacing_around_punctuation_is_exact():
    text = CANONICAL.replace("WARNING: (1)", "WARNING :(1)").replace("General, women", "General ,women")
    assert report(make_lines(wrapped(text))).exact


def test_capitals_with_a_dropped_comma_is_noise_with_a_short_diff():
    text = CANONICAL.upper().replace("GENERAL, WOMEN", "GENERAL WOMEN")
    r = report(make_lines(wrapped(text)))
    assert not r.exact and r.assessment == "noise"
    assert r.diff and "General," in r.diff and len(r.diff) < 60  # case alone must not flood the diff


def test_one_word_substitution_is_a_wording_change_not_noise():
    text = CANONICAL.replace("may cause health problems", "can cause health problems")
    assert classify_difference(CANONICAL, text) == "wording"
    r = report(make_lines(wrapped(text)))
    assert r.present and not r.exact
    assert r.assessment == "wording"  # the verdict treats this as an issue, not a review item
    assert "-may" in r.diff and "+can" in r.diff


def test_missing_clause_number_is_a_wording_change():
    text = CANONICAL.replace("(2) Consumption", "Consumption")
    assert classify_difference(CANONICAL, text) == "wording"


def test_dropped_colon_or_comma_is_noise():
    assert classify_difference(CANONICAL, CANONICAL.replace("WARNING:", "WARNING")) == "noise"
    assert classify_difference(CANONICAL, CANONICAL.replace("General,", "General")) == "noise"
    r = report(make_lines(wrapped(CANONICAL.replace("WARNING:", "WARNING"))))
    assert r.present and not r.exact
    assert r.assessment == "noise"


def test_ocr_confusable_inside_a_word_is_noise():
    text = CANONICAL.replace("Surgeon", "Surge0n").replace("machinery", "machlnery")
    assert classify_difference(CANONICAL, text) == "noise"


def test_small_print_slips_seen_on_approved_labels_are_noise():
    """From the real-label sample: a transposition, an added or dropped letter in a four-letter word,
    and a lot number swept in from the next line. All Needs review with a diff, none an issue."""
    assert classify_difference(CANONICAL, CANONICAL.replace("Surgeon", "Suregon")) == "noise"
    assert classify_difference(CANONICAL, CANONICAL.replace("your ability", "yours ability")) == "noise"
    assert classify_difference(CANONICAL, CANONICAL.replace("to drive", "to rive")) == "noise"
    assert classify_difference(CANONICAL, CANONICAL.replace("women", "woman")) == "noise"
    assert classify_difference(CANONICAL, CANONICAL.replace("(2) Consumption", "26 (2) Consumption")) == "noise"
    # still wording: a word replaced or dropped
    assert classify_difference(CANONICAL, CANONICAL.replace("may cause", "can cause")) == "wording"
    assert classify_difference(CANONICAL, CANONICAL.replace("of the risk", "of risk")) == "wording"


def test_hyphenated_line_break_in_capitals_is_repaired():
    head = "GOVERNMENT WARNING: "
    caps = head + CANONICAL[len(head) :].upper()
    lines = make_lines(
        [
            "GOVERNMENT WARNING: (1) ACCORDING TO THE SURGEON GENERAL,",
            "WOMEN SHOULD NOT DRINK ALCOHOLIC BEVERAGES DURING PREG-",
            "NANCY BECAUSE OF THE RISK OF BIRTH DEFECTS. (2) CONSUMP-",
            "TION OF ALCOHOLIC BEVERAGES IMPAIRS YOUR ABILITY TO DRIVE",
            "A CAR OR OPERATE MACHINERY, AND MAY CAUSE HEALTH PROBLEMS.",
        ]
    )
    assert report(lines).exact, caps


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


def test_small_text_misreads_are_noise_not_wording():
    """Seen on real OCR output: '(1)' read as '(i)', 'drive' read with one wrong letter."""
    text = CANONICAL.replace("(1)", "(i)").replace("drive", "driv\u010d")
    assert classify_difference(CANONICAL, text) == "noise"
    r = report(make_lines(wrapped(text)))
    assert r.assessment == "noise" and not r.exact


def test_accented_letter_in_the_read_is_noise_not_exact():
    """The regulation text has no accents; 'alcoholi\u010d' is almost certainly a recognition artifact,
    but exact means exact, so the agent confirms it."""
    r = report(make_lines(wrapped(CANONICAL.replace("alcoholic beverages during", "alcoholi\u010d beverages during"))))
    assert not r.exact and r.assessment == "noise"


def test_missing_warning_has_absent_assessment():
    assert report(make_lines(["OLD TOM DISTILLERY"])).assessment == "absent"


def test_warning_alone_is_not_an_anchor():
    lines = make_lines(["WARNING: keep out of reach of children.", "Contains sulfites."])
    assert find_warning(lines) is None
    assert report(lines).assessment == "absent"


def test_continuation_lines_must_share_the_anchor_column():
    from tests.unit.conftest import make_line

    left = wrapped(CANONICAL, 50)
    lines = [make_line(t, y=100 + i * 44, x=100, h=34) for i, t in enumerate(left)]
    # a second column of unrelated text at the same heights must not be swept into the span
    lines += [make_line("Tasting notes: oak, vanilla, caramel", y=100 + i * 44, x=1600, h=34) for i in range(len(left))]
    r = report(lines)
    assert r.exact, r.diff


def test_word_boundary_changes_are_never_exact():
    """Spacing is ignored only next to punctuation. A boundary moved between letters changes the
    words: it is a slip for a person to check, never a pass (review 005, item 1.1)."""
    moved = report(make_lines(wrapped(CANONICAL.replace("women should", "womens hould"))))
    assert not moved.exact and moved.assessment == "noise" and moved.diff and "womens" in moved.diff
    merged = report(make_lines(wrapped(CANONICAL.replace("a car", "acar"))))
    assert not merged.exact and merged.assessment == "noise"
    split = report(make_lines(wrapped(CANONICAL.replace("GOVERNMENT WARNING", "GOVERN MENT WARNING"))))
    assert split.present and not split.exact
