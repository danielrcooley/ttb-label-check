from app.pipeline.normalize import (
    case_only_difference,
    fold,
    fold_digits,
    join_hyphenated,
    key,
)


def test_fold_treats_case_and_curly_apostrophe_as_same_text():
    assert fold("STONE’S THROW") == fold("Stone's Throw")


def test_fold_strips_diacritics_but_keeps_letters():
    assert fold("Château Belmont") == "chateau belmont"


def test_key_keeps_only_letters_and_digits_and_drops_apostrophes():
    assert key("Old Tom's Distillery!") == "old toms distillery"
    assert key("STONE'S THROW") == key("Stones Throw")


def test_fold_digits_repairs_confusables_only_in_numeric_tokens():
    assert fold_digits("7S0 mL") == "750 mL"
    assert fold_digits("9O PROOF") == "90 PROOF"
    assert fold_digits("ALC. 45% BY VOL.") == "ALC. 45% BY VOL."
    assert fold_digits("OLD TOM") == "OLD TOM"


def test_join_hyphenated_repairs_line_break_hyphenation_for_letter_continuations():
    assert join_hyphenated(["during preg-", "nancy because"]) == "during pregnancy because"
    assert join_hyphenated(["(2) CONSUMP-", "TION OF ALCOHOLIC"]) == "(2) CONSUMPTION OF ALCOHOLIC"  # capitals too
    assert join_hyphenated(["750 mL -", "12 FL OZ"]) == "750 mL - 12 FL OZ"  # a continuation must start with a letter
    assert join_hyphenated(["", "  a  ", "b"]) == "a b"


def test_case_only_difference():
    assert case_only_difference("STONE'S THROW", "Stone's Throw")
    assert not case_only_difference("STONE'S THROW", "STONE'S THROW")
    assert not case_only_difference("STONES THROW", "Stone's Throw")
