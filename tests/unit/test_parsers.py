import pytest
from app.pipeline.parsers import (
    alcohol_matches,
    alcohol_statement_required,
    is_standard_fill,
    parse_alcohol,
    parse_volumes,
    volumes_match,
)
from app.schemas import BeverageType


@pytest.mark.parametrize(
    ("text", "percent", "proof"),
    [
        ("45% Alc./Vol. (90 Proof)", 45.0, 90.0),
        ("40% ALC/VOL (80 PROOF)", 40.0, 80.0),
        ("Alc. 40% by Vol.", 40.0, None),
        ("ABV 5.2%", 5.2, None),
        ("13,5% vol", 13.5, None),
        ("ALCOHOL 13.5% BY VOLUME", 13.5, None),
        ("Alcohol 14.1 percent by volume", 14.1, None),
        ("90 PROOF", 45.0, 90.0),
        ("14.1% Alc./Vol.", 14.1, None),
        ("6.8% ALC/VOL", 6.8, None),
    ],
)
def test_parse_alcohol_formats(text, percent, proof):
    got = parse_alcohol(text)
    assert got is not None
    assert got.percent == pytest.approx(percent)
    assert got.proof == proof


def test_parse_alcohol_repairs_ocr_confusables_in_numbers():
    got = parse_alcohol("4S% ALC/VOL (9O PROOF)")
    assert got and got.percent == 45.0 and got.proof == 90.0


def test_parse_alcohol_bare_number_only_when_allowed():
    assert parse_alcohol("45") is None
    got = parse_alcohol("45", allow_bare=True)
    assert got and got.percent == 45.0


def test_parse_alcohol_ignores_years_and_noise():
    assert parse_alcohol("EST. 1925 KENTUCKY") is None
    assert parse_alcohol("OLD TOM DISTILLERY") is None


def test_alcohol_consistency_between_percent_and_proof():
    assert parse_alcohol("45% Alc./Vol. (90 Proof)").consistent is True
    assert parse_alcohol("45% Alc./Vol. (80 Proof)").consistent is False
    assert parse_alcohol("45% Alc./Vol.").consistent is None


def test_alcohol_matches_within_tolerance():
    a, b = parse_alcohol("45% alc/vol"), parse_alcohol("45.0% ALC. BY VOL.")
    assert alcohol_matches(a, b)
    assert not alcohol_matches(a, parse_alcohol("40% alc/vol"))


@pytest.mark.parametrize(
    ("text", "mls"),
    [
        ("750 mL", [750.0]),
        ("750ML", [750.0]),
        ("1 L", [1000.0]),
        ("1.75 L", [1750.0]),
        ("75 cl", [750.0]),
        ("0,75 L", [750.0]),
        ("1,750 mL", [1750.0]),
        ("12 FL OZ (355 mL)", [354.88, 355.0]),
        ("16 FL. OZ.", [473.18]),
        ("1 PINT", [473.18]),
        ("7S0 mL", [750.0]),
    ],
)
def test_parse_volumes_formats(text, mls):
    got = [v.ml for v in parse_volumes(text)]
    assert got == pytest.approx(mls, abs=0.01)


def test_parse_volumes_ignores_non_volume_text():
    assert parse_volumes("EST. 1925 Kentucky Straight Bourbon") == []
    assert parse_volumes("45% Alc./Vol. (90 Proof)") == []
    assert parse_volumes("OLD TOM DISTILLERY") == []


def test_volumes_match_allows_unit_conversion_rounding():
    assert volumes_match(750, 751.2)
    assert volumes_match(355, 354.88)
    assert not volumes_match(750, 700)


@pytest.mark.parametrize(
    ("bev", "ml", "expected"),
    [
        (BeverageType.spirits, 750, True),
        (BeverageType.spirits, 331, True),  # added January 2025
        (BeverageType.spirits, 740, False),
        (BeverageType.wine, 187, True),
        (BeverageType.wine, 5000, True),  # 4 L and larger in even liters
        (BeverageType.wine, 4500, False),
        (BeverageType.malt, 355, None),
    ],
)
def test_standards_of_fill(bev, ml, expected):
    assert is_standard_fill(bev, ml) is expected


def test_alcohol_statement_requirements_by_beverage_type():
    assert alcohol_statement_required(BeverageType.spirits, "Vodka")[0] is True
    assert alcohol_statement_required(BeverageType.wine, "Table Wine")[0] is False
    assert alcohol_statement_required(BeverageType.wine, "Cabernet Sauvignon")[0] is True
    assert alcohol_statement_required(BeverageType.malt, "India Pale Ale")[0] is False
