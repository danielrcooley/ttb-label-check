"""Rules tightened after review 007 (D-045): the bottler name at word boundaries with the address
read next to it, street forms without a number, the table/light wine exemption, an unread net
contents statement, and the load tool's percentile."""

from __future__ import annotations

import pytest
from app.config import Settings
from app.pipeline.compare import bottler_check, compare
from app.pipeline.normalize import split_registered_party
from app.pipeline.parsers import alcohol_statement_required
from app.schemas import ApplicationFields, BeverageType

from tests.unit.conftest import make_lines


def _bottler(expected: str, label_lines: list[str]):
    return bottler_check(expected, make_lines(label_lines), Settings(ocr_workers=1))


def test_bottler_name_inside_another_word_is_not_a_match():
    """'ACE' is not printed whole inside 'PALACE'; a city and a state elsewhere on the label do
    not corroborate it (review 007, 2.1)."""
    c = _bottler("ACE WINES, 100 Main St, Napa, CA, 94558", ["BOTTLED BY PALACE WINES", "NAPA VALLEY", "CALIFORNIA"])
    assert c.status != "match", c


def test_bottler_address_is_the_city_and_state_together_or_both_next_to_the_bottler_line():
    """A line carrying the city and the state together is an address line wherever it is printed
    (labels put it on the other side of the package); a bare state name far from the name is not
    (on a wine label it is the appellation)."""
    registered = "Green Cheek Beer Company, Green Cheek Beer Company, Inc., 2957 RANDOLPH ST, Costa Mesa, CA, 92626"
    scattered = _bottler(
        registered,
        ["COSTA MESA", "FINE ALE", "12 FL OZ", "HOPS", "MALT", "WATER", "CALIFORNIA", "BREWED BY GREEN CHEEK BEER CO."],
    )
    assert scattered.status == "needs_review" and "Costa Mesa" in (scattered.note or ""), scattered
    near = _bottler(registered, ["FINE ALE", "BREWED BY GREEN CHEEK BEER CO.", "COSTA MESA", "CA"])
    assert near.status == "match", near
    other_side = bottler_check(
        registered,
        [
            *make_lines(["BREWED BY GREEN CHEEK BEER CO.", "12 FL OZ"], image_index=1),
            *make_lines(["FINE ALE", "COSTA MESA, CA"]),
        ],
        Settings(ocr_workers=1),
    )
    assert other_side.status == "match", other_side


def test_registered_street_without_a_number_and_a_line_ending_city_state_zip_still_yield_the_address():
    party = split_registered_party("Trade Name, Legal Name Inc., One Winery Road, Napa, CA, 94558")
    assert (party.city, party.state, party.zip_code) == ("Napa", "CA", "94558")
    assert "One Winery Road" not in party.names and party.names[0] == "Trade Name"
    party = split_registered_party("Trade Name, Legal Name Inc., Napa, CA, 94558")
    assert (party.city, party.state, party.zip_code) == ("Napa", "CA", "94558")


@pytest.mark.parametrize(
    ("class_type", "required"),
    [
        ("Table Wine", False),
        ("Light Wine", False),
        ("Table Red Wine", False),
        ("Red Table Wine", False),
        ("Light Rosé Wine", False),
        ("Light Sparkling Wine", True),  # review 007: not a designation 27 CFR 4.36 names
        ("Table Dessert Wine", True),
        ("Sparkling Wine", True),
    ],
)
def test_only_the_named_table_and_light_wine_designations_exempt_the_alcohol_statement(class_type, required):
    assert alcohol_statement_required(BeverageType.wine, class_type)[0] is required


def test_net_contents_given_but_not_read_is_review_not_an_issue():
    """An unread statement is a heuristic miss (the same rule as an unread alcohol statement,
    D-041): Needs review with the application's value in the note, never Issues on its own."""
    app = ApplicationFields(
        beverage_type="spirits",
        brand_name="OLD TOM",
        class_type="Bourbon",
        alcohol_content="45%",
        net_contents="750 mL",
    )
    result = compare(app, make_lines(["OLD TOM", "BOURBON", "45% ALC/VOL"]), [], Settings(ocr_workers=1))
    net = next(c for c in result.checks if c.id == "net_contents")
    assert net.status == "needs_review" and "750 mL" in (net.note or "")
    # the missing warning statement is the issue here; net contents is only asked to be confirmed
    issues, _, confirm = result.summary.partition("Also confirm")
    assert "net contents" not in issues and "net contents" in confirm


def test_load_tool_percentile_is_nearest_rank():
    from tools.loadtest import pct

    assert pct([float(i) for i in range(1, 11)], 0.95) == 10.0
    assert pct([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert pct([7.0], 0.95) == 7.0
    assert pct([], 0.95) == 0.0
