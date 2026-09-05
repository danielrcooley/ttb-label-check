"""Review 009 (the final whole-repository pass): behaviours that were wrong and are now pinned."""

from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest
from app.config import Settings
from app.csvio import parse_csv
from app.pipeline.compare import compare
from app.pipeline.countries import country_named
from app.pipeline.images import decode_image
from app.pipeline.parsers import parse_alcohol, parse_volumes
from app.schemas import ApplicationFields, BeverageType
from PIL import Image, ImageDraw

from tests.unit.conftest import make_lines

S = Settings(ocr_workers=1)


def _check(app: ApplicationFields, label_lines: list[str], check_id: str):
    return next(c for c in compare(app, make_lines(label_lines), [], S).checks if c.id == check_id)


# ----------------------------------------------------------------------------- alcohol content
def test_an_alcohol_value_the_tool_cannot_read_is_review_not_no_value():
    """'six percent' in the application is a value; it must not pass as Info on the way to Ready."""
    app = ApplicationFields(
        beverage_type="malt", brand_name="X", class_type="India Pale Ale", alcohol_content="six percent"
    )
    c = _check(app, ["X", "INDIA PALE ALE", "6.8% ALC/VOL", "12 FL OZ"], "alcohol_content")
    assert c.status == "needs_review"
    assert "six percent" in (c.note or "") and "6.8%" in (c.note or "")


def test_a_label_contradicting_itself_is_review_even_when_the_application_gives_no_value():
    app = ApplicationFields(beverage_type="malt", brand_name="X", class_type="India Pale Ale", alcohol_content=None)
    c = _check(app, ["X", "INDIA PALE ALE", "40% ALC/VOL", "45% ALC/VOL"], "alcohol_content")
    assert c.status == "needs_review" and "different values" in (c.note or "")


def test_a_blank_alcohol_value_for_an_optional_class_stays_info():
    app = ApplicationFields(beverage_type="malt", brand_name="X", class_type="India Pale Ale", alcohol_content=None)
    c = _check(app, ["X", "INDIA PALE ALE", "6.8% ALC/VOL"], "alcohol_content")
    assert c.status == "info"


# ----------------------------------------------------------------------------- country of origin
def test_a_us_state_on_a_bottling_line_is_not_evidence_against_an_import():
    """'Bottled in Napa, CA' names a place, not a country: an Italian wine bottled in California is
    a question for the person (D-045), never a Mismatch."""
    app = ApplicationFields(
        beverage_type="wine", brand_name="X", class_type="Red Wine", country_of_origin="Italy", imported=True
    )
    c = _check(app, ["X", "RED WINE", "750 mL", "Bottled in Napa, CA"], "country_of_origin")
    assert c.status == "needs_review" and c.found == "Bottled in Napa, CA"


def test_a_country_named_on_the_origin_line_is_still_a_mismatch():
    app = ApplicationFields(
        beverage_type="wine", brand_name="X", class_type="Red Wine", country_of_origin="Italy", imported=True
    )
    c = _check(app, ["X", "RED WINE", "750 mL", "Product of France"], "country_of_origin")
    assert c.status == "mismatch" and "France" in (c.note or "")


def test_a_state_still_matches_a_domestic_application():
    app = ApplicationFields(beverage_type="wine", brand_name="X", class_type="Red Wine", country_of_origin="USA")
    c = _check(app, ["X", "RED WINE", "750 mL", "Bottled in Napa, CA"], "country_of_origin")
    assert c.status == "match"


def test_country_named_without_states_ignores_state_names_and_codes_but_not_countries():
    assert country_named("Napa, CA", states=False) is None
    assert country_named("Bardstown, Kentucky", states=False) is None
    assert country_named("Product of Georgia", states=False) == "Georgia"
    assert country_named("Product of France", states=False) == "France"
    assert country_named("Product of USA", states=False) == "United States"


# ----------------------------------------------------------------------------- numbers
@pytest.mark.parametrize("text", ["17500 mL", "1045% ALC/VOL"])
def test_a_number_is_never_read_from_the_tail_of_a_longer_number(text):
    assert parse_volumes(text) == [] and parse_alcohol(text) is None


def test_common_sizes_and_statements_still_parse():
    assert [v.ml for v in parse_volumes("1750 mL")] == [1750.0]
    assert [v.ml for v in parse_volumes("NET CONTENTS 1,750 mL")] == [1750.0]
    assert parse_alcohol("45% Alc./Vol. (90 Proof)").percent == 45.0
    assert parse_alcohol("ALC.45% VOL").percent == 45.0  # no space after the period, as OCR often reads it


# ----------------------------------------------------------------------------- spreadsheet
def test_a_bare_number_under_a_proof_header_is_a_proof_not_a_percentage():
    data = b"application_id,beverage_type,brand_name,class_type,proof,net_contents\nA1,spirits,X,Vodka,90,750 mL\n"
    row = parse_csv(data, max_rows=10).rows[0]
    assert row.application is not None and row.application.alcohol_content == "90 proof"
    assert parse_alcohol("90 proof", allow_bare=True).percent == 45.0


def test_a_cell_larger_than_the_csv_module_default_is_a_row_error_not_a_crash():
    """The csv module's default field limit (128 KB) raised csv.Error, a 500, for a file under the
    2 MB upload cap. Now the row is parsed and the oversized value is a per-row validation error."""
    data = b"brand_name,class_type,beverage_type\n" + b"A" * 200_000 + b",Vodka,spirits\n"
    res = parse_csv(data, max_rows=10)
    assert len(res.rows) == 1 and res.rows[0].application is None
    assert any("brand_name" in e for e in res.rows[0].errors)
    notes = b"brand_name,class_type,beverage_type,notes\nX,Vodka,spirits," + b"A" * 200_000 + b"\n"
    ok = parse_csv(notes, max_rows=10).rows[0]  # the long cell in a column the tool does not use
    assert ok.application is not None and ok.application.beverage_type is BeverageType.spirits


# ----------------------------------------------------------------------------- images
def test_artwork_on_a_transparent_background_is_read_on_white():
    im = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 40), "GOVERNMENT WARNING", fill=(0, 0, 0, 255))
    buf = BytesIO()
    im.save(buf, "PNG")
    decoded = decode_image(buf.getvalue(), max_pixels=25_000_000, max_side=1280, filename="t.png")
    arr = np.asarray(decoded.array)
    assert arr.mean() > 200  # mostly white, with dark text on it
    assert arr.min() < 50


def test_a_palette_png_with_transparency_is_read_on_white():
    im = Image.new("RGBA", (120, 60), (0, 0, 0, 0)).convert("P")
    im.info["transparency"] = 0
    buf = BytesIO()
    im.save(buf, "PNG", transparency=0)
    decoded = decode_image(buf.getvalue(), max_pixels=25_000_000, max_side=1280, filename="p.png")
    assert np.asarray(decoded.array).mean() > 200
