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
        ("13.5% vol", 13.5, None),
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


def test_compare_flags_proof_disagreement_and_missing_required_statement():
    from app.config import Settings
    from app.pipeline.compare import compare
    from app.schemas import ApplicationFields

    from tests.unit.conftest import make_lines

    s = Settings(ocr_workers=1)
    lines = make_lines(
        ["OLD TOM DISTILLERY", "Kentucky Straight Bourbon Whiskey", "45% Alc./Vol. (80 Proof)", "750 mL"]
    )
    app = ApplicationFields(
        beverage_type="spirits",
        brand_name="OLD TOM DISTILLERY",
        class_type="Kentucky Straight Bourbon Whiskey",
        alcohol_content="45% Alc./Vol. (90 Proof)",
        net_contents="750 mL",
    )
    alc = next(c for c in compare(app, lines, [], s).checks if c.id == "alcohol_content")
    assert alc.status == "mismatch" and "proof differs" in alc.note

    app2 = app.model_copy(update={"alcohol_content": None})
    alc2 = next(c for c in compare(app2, lines, [], s).checks if c.id == "alcohol_content")
    assert alc2.status == "needs_review"  # required for spirits, missing from the application


def test_compare_prefers_the_alcohol_line_that_matches_the_application():
    from app.config import Settings
    from app.pipeline.compare import compare
    from app.schemas import ApplicationFields

    from tests.unit.conftest import make_lines

    s = Settings(ocr_workers=1)
    lines = make_lines(["Contains 5% alcohol flavoring", "45% ALC/VOL", "750 mL"])
    app = ApplicationFields(
        beverage_type="spirits", brand_name="X", class_type="Vodka", alcohol_content="45%", net_contents="750 mL"
    )
    alc = next(c for c in compare(app, lines, [], s).checks if c.id == "alcohol_content")
    assert alc.status == "match" and alc.found == "45% ALC/VOL"


def test_warning_not_required_below_half_percent():
    from app.config import Settings
    from app.pipeline.compare import compare
    from app.schemas import ApplicationFields

    from tests.unit.conftest import make_lines

    s = Settings(ocr_workers=1)
    lines = make_lines(["NEAR BEER", "Non-alcoholic malt beverage", "0.4% ALC/VOL", "12 FL OZ"])
    app = ApplicationFields(
        beverage_type="malt",
        brand_name="NEAR BEER",
        class_type="Non-alcoholic malt beverage",
        alcohol_content="0.4% ALC/VOL",
        net_contents="12 FL OZ",
    )
    res = compare(app, lines, [], s)
    assert res.warning.assessment == "not_required"
    assert res.verdict == "ready_for_approval"


def test_percent_without_a_volume_marker_is_not_an_alcohol_statement():
    assert parse_alcohol("Contains 5% alcohol flavoring") is None
    assert parse_alcohol("Save 20% today") is None


def test_conflicting_alcohol_statements_across_images_are_a_mismatch():
    from app.config import Settings
    from app.pipeline.compare import compare
    from app.schemas import ApplicationFields

    from tests.unit.conftest import make_lines

    s = Settings(ocr_workers=1)
    front = make_lines(["OLD TOM DISTILLERY", "40% Alc./Vol. (80 Proof)", "750 mL"], image_index=0)
    back = make_lines(["Product of USA", "45% Alc./Vol. (90 Proof) 750 mL"], image_index=1)
    app = ApplicationFields(
        beverage_type="spirits",
        brand_name="OLD TOM DISTILLERY",
        class_type="Bourbon",
        alcohol_content="45% Alc./Vol. (90 Proof)",
        net_contents="750 mL",
    )
    alc = next(c for c in compare(app, front + back, [], s).checks if c.id == "alcohol_content")
    assert alc.status == "mismatch" and "40%" in alc.note and "45%" in alc.note
    assert len(alc.evidence) == 2


def _spirits_app(**over):
    from app.schemas import ApplicationFields

    base = {
        "beverage_type": "spirits",
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Bourbon",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
    }
    base.update(over)
    return ApplicationFields(**base)


def _alc(app, lines):
    from app.config import Settings
    from app.pipeline.compare import compare

    return next(c for c in compare(app, lines, [], Settings(ocr_workers=1)).checks if c.id == "alcohol_content")


def test_wrapped_percent_and_proof_lines_are_one_statement():
    from tests.unit.conftest import make_lines

    lines = make_lines(["OLD TOM DISTILLERY", "Bourbon", "45% Alc./Vol.", "(90 Proof)", "750 mL"])
    alc = _alc(_spirits_app(), lines)
    assert alc.status == "match" and "45" in alc.note
    # the two halves disagree: that is one inconsistent statement (review), not two contradicting labels
    lines = make_lines(["OLD TOM DISTILLERY", "Bourbon", "45% Alc./Vol.", "(80 Proof)", "750 mL"])
    alc = _alc(_spirits_app(alcohol_content="45% Alc./Vol."), lines)
    assert alc.status == "needs_review" and "does not equal twice" in alc.note
    # and when the application states a proof, a different proof on the label is a mismatch
    alc = _alc(_spirits_app(), lines)
    assert alc.status == "mismatch" and "proof differs" in alc.note


def test_equal_percents_with_conflicting_proofs_are_a_mismatch():
    from tests.unit.conftest import make_lines

    front = make_lines(["OLD TOM DISTILLERY", "45% ALC/VOL (90 PROOF)"], image_index=0)
    back = make_lines(["45% ALC/VOL (80 PROOF)", "750 mL"], image_index=1)
    alc = _alc(_spirits_app(), front + back)
    assert alc.status == "mismatch" and "different proofs" in alc.note


def test_proof_only_statement_still_matches_the_application():
    from tests.unit.conftest import make_lines

    alc = _alc(_spirits_app(), make_lines(["OLD TOM DISTILLERY", "90 PROOF", "750 mL"]))
    assert alc.status == "match"


def test_zero_percent_parses_and_exempts_the_warning():
    from app.config import Settings
    from app.pipeline.compare import compare
    from app.schemas import ApplicationFields

    from tests.unit.conftest import make_lines

    assert parse_alcohol("0.0% ALC/VOL").percent == 0.0
    lines = make_lines(["NEAR BEER", "Non-alcoholic malt beverage", "0.0% ALC/VOL", "12 FL OZ"])
    app = ApplicationFields(
        beverage_type="malt",
        brand_name="NEAR BEER",
        class_type="Non-alcoholic malt beverage",
        alcohol_content="0.0%",
        net_contents="12 FL OZ",
    )
    res = compare(app, lines, [], Settings(ocr_workers=1))
    assert res.warning.assessment == "not_required"
    assert res.verdict == "ready_for_approval" and "no health warning" in res.summary


def test_bottler_as_registered_matches_the_label_as_printed():
    """Real labels prefix and abbreviate ("Brewed by GREEN CHEEK BEER CO."); applications spell out."""
    from app.config import Settings
    from app.pipeline.compare import bottler_check
    from app.pipeline.normalize import fold_company

    from tests.unit.conftest import make_lines

    assert fold_company("Brewed & Packaged by GREEN CHEEK BEER CO.") == "green cheek beer"
    assert fold_company("Green Cheek Beer Company, LLC") == "green cheek beer"
    assert fold_company("Imported by: T. Elenteny Imports, New York, NY") == "t elenteny imports new york ny"
    s = Settings(ocr_workers=1)
    lines = make_lines(["BREWED BY GREEN CHEEK BEER CO.", "ORANGE, CA", "12 FL OZ"])
    check = bottler_check("Green Cheek Beer Company, Orange, CA", lines, s)
    assert check.status == "match", check
    assert check.found == "BREWED BY GREEN CHEEK BEER CO. ORANGE, CA" and "Label says" in (check.note or "")
    assert check.expected == "Green Cheek Beer Company, Orange, CA"
    # a different company is still a difference
    other = bottler_check(
        "T. Elenteny Holdings, LLC", make_lines(["IMPORTED BY: T. ELENTENY IMPORTS", "NEW YORK, NY"]), s
    )
    assert other.status in ("mismatch", "needs_review")


def test_unparseable_required_field_blocks_ready_and_omitted_optional_fields_do_not():
    from app.config import Settings
    from app.pipeline.compare import compare
    from app.pipeline.warning import CANONICAL

    from tests.unit.conftest import make_lines

    s = Settings(ocr_workers=1)
    lines = make_lines(["OLD TOM DISTILLERY", "Bourbon", "45% Alc./Vol. (90 Proof)", "750 mL", CANONICAL])
    # bottler and country of origin omitted from the application: not compared, Ready still allowed
    res = compare(_spirits_app(), lines, [], s)
    assert res.warning.exact, res.warning
    assert {c.status for c in res.checks if c.id in ("bottler", "country_of_origin")} == {"not_checked"}
    assert res.verdict == "ready_for_approval"
    # a required value the tool cannot interpret must never be silently skipped
    res = compare(_spirits_app(net_contents="seven fifty"), lines, [], s)
    net = next(c for c in res.checks if c.id == "net_contents")
    assert net.status == "needs_review"
    assert res.verdict == "needs_review" and "net contents" in res.summary
    # imported without a stated country of origin is a question for the agent, not a pass
    res = compare(_spirits_app(imported=True), lines, [], s)
    assert next(c for c in res.checks if c.id == "country_of_origin").status == "needs_review"
    assert res.verdict == "needs_review"
