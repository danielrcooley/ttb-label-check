from app.csvio import parse_csv, template_csv
from app.schemas import BeverageType


def test_template_round_trips_through_the_parser():
    res = parse_csv(template_csv().encode("utf-8"), max_rows=100)
    assert res.rows and not res.rows[0].errors
    app = res.rows[0].application
    assert app.brand_name == "OLD TOM DISTILLERY" and app.beverage_type is BeverageType.spirits
    assert res.rows[0].images == ["COLA-2026-000123_front.png", "COLA-2026-000123_back.png"]


def test_header_aliases_and_semicolon_delimiter_from_european_excel():
    data = b"ID;Brand;Class/Type;ABV;Net Contents;Type\nA1;Blue Heron;Chardonnay;14,1% Alc./Vol.;750 mL;Wine\n"
    res = parse_csv(data, max_rows=100)
    assert res.delimiter == ";"
    assert res.rows[0].application.brand_name == "Blue Heron"
    assert res.rows[0].application.beverage_type is BeverageType.wine
    assert res.rows[0].application.alcohol_content == "14,1% Alc./Vol."


def test_utf8_bom_and_cp1252_are_both_accepted():
    bom = "﻿brand_name,class_type,net_contents,beverage_type\nChâteau,Red Wine,750 mL,wine\n".encode()
    assert parse_csv(bom, max_rows=10).rows[0].application.brand_name == "Château"
    cp = "brand_name,class_type,net_contents,beverage_type\nChâteau,Red Wine,750 mL,wine\n".encode("cp1252")
    res = parse_csv(cp, max_rows=10)
    assert res.rows[0].application.brand_name == "Château"
    assert any("Windows-1252" in w for w in res.warnings)


def test_beverage_type_inferred_from_class_when_column_missing_and_errors_are_per_row():
    data = (
        b"brand_name,class_type,net_contents\n"
        b"Old Tom,Kentucky Straight Bourbon Whiskey,750 mL\n"
        b"Mystery,Unknown Thing,750 mL\n"
        b",Vodka,750 mL\n"
    )
    res = parse_csv(data, max_rows=100)
    assert res.rows[0].application.beverage_type is BeverageType.spirits and not res.rows[0].errors
    assert res.rows[1].application is None and "beverage_type" in res.rows[1].errors[0]
    assert res.rows[2].application is None and any("brand_name" in e for e in res.rows[2].errors)


def test_blank_rows_skipped_and_row_limit_applied():
    data = (
        "brand_name,class_type,net_contents,beverage_type\n"
        + "\n".join(f"B{i},Vodka,750 mL,spirits" for i in range(10))
        + "\n\n\n"
    )
    res = parse_csv(data.encode(), max_rows=3)
    assert len(res.rows) == 3 and any("first 3 rows" in w for w in res.warnings)


def test_imported_flag_variants():
    data = b"brand_name,class_type,net_contents,beverage_type,imported,country_of_origin\nA,Vodka,750 mL,spirits,Yes,France\nB,Vodka,750 mL,spirits,,\n"
    rows = parse_csv(data, max_rows=10).rows
    assert rows[0].application.imported is True and rows[1].application.imported is False
