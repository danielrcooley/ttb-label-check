"""Which country an origin statement names (D-045): a hard origin mismatch needs a real country."""

from __future__ import annotations

import pytest
from app.config import Settings
from app.pipeline.compare import compare
from app.pipeline.countries import country_named
from app.schemas import ApplicationFields

from tests.unit.conftest import make_lines


@pytest.mark.parametrize(
    ("text", "country"),
    [
        ("Product of France", "France"),
        ("PRODUCED AND BOTTLED IN ITALY", "Italy"),
        ("Product of the Netherlands", "Netherlands"),
        ("Product of Holland", "Netherlands"),
        ("Product of Scotland", "United Kingdom"),
        ("Product of U.S.A.", "United States"),
        ("Product of USA", "United States"),
        ("Bottled in Napa, CA", "United States"),
        ("Bottled in Bardstown, Kentucky", "United States"),
        ("Atlanta, Georgia", "United States"),
        ("Product of Georgia", "Georgia"),
        ("Product of Papua New Guinea", "Papua New Guinea"),
        ("Product of the Dominican Republic", "Dominican Republic"),
        ("Product of Republic of Korea", "South Korea"),
        ("Napa Valley", None),
        ("", None),
    ],
)
def test_country_named(text, country):
    assert country_named(text) == country


def _origin(expected: str, label_lines: list[str]):
    app = ApplicationFields(
        beverage_type="wine",
        brand_name="X",
        class_type="Red Wine",
        net_contents="750 mL",
        country_of_origin=expected,
        imported=True,
    )
    return next(
        c
        for c in compare(app, make_lines(["X", "RED WINE", "750 mL", *label_lines]), [], Settings(ocr_workers=1)).checks
        if c.id == "country_of_origin"
    )


def test_a_place_that_is_not_a_country_is_review_not_a_mismatch():
    """Review 007: 'Bottled in Napa, CA' proves nothing about an Italian wine's origin statement;
    it is a review item with the line shown, not an issue."""
    c = _origin("Italy", ["Bottled in Napa Valley"])
    assert c.status == "needs_review" and "cannot match" in (c.note or "") and c.found == "Bottled in Napa Valley"


def test_another_country_named_is_a_mismatch_and_the_same_country_in_another_form_is_a_match():
    other = _origin("Italy", ["Product of France"])
    assert other.status == "mismatch" and "France" in (other.note or "")
    same = _origin("United Kingdom", ["Product of Scotland"])
    assert same.status == "match" and same.found == "Product of Scotland"
    domestic = _origin("USA", ["Bottled in Napa, CA"])
    assert domestic.status == "match"


def test_an_unknown_expected_country_never_produces_a_mismatch():
    c = _origin("Atlantis", ["Product of France"])
    assert c.status == "needs_review"


def test_georgia_on_a_domestic_application_is_ambiguous_and_goes_to_review():
    """Seen in the real tally: a Georgia-state wine ("Made in Georgia") against a domestic
    application. Georgia is a state and a country; with a U.S. application that is a question for
    the person, not an issue. Against a foreign application it is still the country."""
    c = _origin("USA", ["Made in Georgia"])
    assert c.status == "needs_review" and "state" in (c.note or ""), c
    assert _origin("Italy", ["Product of Georgia"]).status == "mismatch"
