from app.pipeline.extract import extract_fields

from tests.unit.conftest import make_lines


def test_extract_only_mode_reads_origin_bottler_alcohol_volume_and_warning():
    from app.pipeline.warning import CANONICAL

    lines = make_lines(
        [
            "OLD TOM DISTILLERY",
            "Distilled and Bottled by Old Tom Distillery, Bardstown, Kentucky",
            "Product of USA",
            "45% Alc./Vol. (90 Proof) 750 mL",
            *CANONICAL.split(". "),
        ]
    )
    f = extract_fields(lines)
    assert f.origin_lines == ["Product of USA"]
    assert f.bottler_lines and f.bottler_lines[0].startswith("Distilled and Bottled by")
    assert f.alcohol_percent == 45.0 and f.proof == 90.0
    assert f.net_contents_ml == [750.0]
    assert f.largest_text == "Distilled and Bottled by Old Tom Distillery, Bardstown, Kentucky"


def test_origin_pattern_requires_whole_words():
    f = extract_fields(make_lines(["byproduct of fermentation"]))
    assert f.origin_lines == []
