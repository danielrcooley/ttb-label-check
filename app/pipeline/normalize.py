"""Text normalization.

Three deliberately different levels:

- ``fold``: what a human would call "the same text": Unicode compatibility forms, diacritics,
  quote and dash families, case, whitespace. Used to decide "Match with a note".
- ``key``: letters and digits only. Used for fuzzy scoring so punctuation noise from OCR does not
  dominate the score. Never used to decide a Match on its own.
- ``fold_digits``: OCR confusables mapped to digits, applied only to tokens that look numeric.
  Used by the parsers, never for display.

The government warning check uses only ``collapse_ws``, ``unify_punctuation``, ``join_hyphenated``
and ``fold`` (for locating the statement); exactness there compares every word and punctuation mark
and ignores only letter case and spacing next to punctuation (see warning.py).
"""

from __future__ import annotations

import re
import unicodedata

_QUOTES = {
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
    "′": "'",
    "`": "'",
    "´": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "″": '"',
    "‐": "-",
    "‑": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "−": "-",
    " ": " ",  # noqa: RUF001
}
_QUOTE_TABLE = str.maketrans(_QUOTES)
_WS = re.compile(r"\s+")
_APOSTROPHES = re.compile(r"['\"]")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Confusables in numeric context. Keys are characters OCR emits for digits.
_TO_DIGIT = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "Q": "0",
        "D": "0",
        "I": "1",
        "l": "1",
        "|": "1",
        "!": "1",
        "S": "5",
        "s": "5",
        "B": "8",
        "Z": "2",
        "z": "2",
        "G": "6",
    }
)
# A run of digits and digit-lookalikes (with decimal separators). Repaired only if it holds a real digit.
_DIGITISH = re.compile(r"[0-9OoQDIl|!SsBZzG][0-9OoQDIl|!SsBZzG.,]*")


def strip_diacritics(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def unify_punctuation(s: str) -> str:
    return unicodedata.normalize("NFKC", s).translate(_QUOTE_TABLE)


def collapse_ws(s: str) -> str:
    return _WS.sub(" ", s).strip()


def fold(s: str) -> str:
    """Case-, accent-, quote- and whitespace-insensitive form. Keeps punctuation otherwise."""
    return collapse_ws(strip_diacritics(unify_punctuation(s)).casefold())


def key(s: str) -> str:
    """Letters and digits only, single-spaced. Apostrophes are dropped, not split ("Stone's" -> "stones")."""
    return collapse_ws(_NON_ALNUM.sub(" ", _APOSTROPHES.sub("", fold(s))))


def fold_digits(s: str) -> str:
    """Map OCR confusables to digits inside runs that contain at least one real digit.

    "45% AIc./VoI." -> unchanged letters ; "7S0 mL" -> "750 mL" ; "(9O PROOF)" -> "(90 PROOF)" ; "OLD" -> "OLD".
    """

    def repair(m: re.Match[str]) -> str:
        tok = m.group(0)
        return tok.translate(_TO_DIGIT) if any(ch.isdigit() for ch in tok) else tok

    return _DIGITISH.sub(repair, s)


def join_hyphenated(lines: list[str]) -> str:
    """Join OCR lines into one string, repairing end-of-line hyphenation ("preg-" + "nancy")."""
    parts: list[str] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if parts and parts[-1].endswith("-") and ln[:1].isalpha():  # "preg-" + "nancy", "CONSUMP-" + "TION"
            parts[-1] = parts[-1][:-1] + ln
        else:
            parts.append(ln)
    return collapse_ws(" ".join(parts))


_BY_PREFIX = re.compile(
    r"^\W*(?:(?:hand[- ]?)?(?:distilled|bottled|brewed|produced|vinted|cellared|made|packaged|imported|blended|"
    r"crafted|manufactured|filled|canned|fermented)"
    r"(?:\s*(?:,|&|and|\+)\s*(?:distilled|bottled|brewed|produced|vinted|cellared|made|packaged|imported|blended|"
    r"crafted|manufactured|filled|canned|fermented))*"
    r"\s+(?:by|for)\b\s*:?\s*)",
    re.I,
)
_CORPORATE_TOKENS = frozenset(
    {"company", "co", "incorporated", "inc", "corporation", "corp", "limited", "ltd", "llc", "lp", "llp", "the"}
)


_FORM_CANON = {
    "company": "Company",
    "co": "Company",
    "incorporated": "Inc.",
    "inc": "Inc.",
    "corporation": "Corp.",
    "corp": "Corp.",
    "limited": "Ltd.",
    "ltd": "Ltd.",
    "llc": "LLC",
    "lp": "LP",
    "llp": "LLP",
}


def fold_company(s: str) -> str:
    """A company name as registered vs as printed: drops a "Bottled by" style prefix and corporate
    forms (Company, Co., LLC, Inc.), then keeps letters and digits like ``key``.
    "Brewed by GREEN CHEEK BEER CO." and "Green Cheek Beer Company" both become "green cheek beer".
    Whether the forms themselves agree is a separate question: ``company_forms``."""
    words = [w for w in key(_BY_PREFIX.sub("", s)).split(" ") if w and w not in _CORPORATE_TOKENS]
    return " ".join(words)


def company_forms(s: str) -> frozenset[str]:
    """The corporate forms named in a company line, spelled one way ("Co." and "Company" are the
    same form; "LLC" and "Inc." are not). An omitted form is no difference in who bottled it, but
    two different forms name two different legal entities and are left to the person."""
    return frozenset(_FORM_CANON[w] for w in key(s).split(" ") if w in _FORM_CANON)


def case_only_difference(a: str, b: str) -> bool:
    """True when a and b differ only by case (after whitespace collapse)."""
    return collapse_ws(a) != collapse_ws(b) and collapse_ws(a).casefold() == collapse_ws(b).casefold()
