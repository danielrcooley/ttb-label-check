"""Parsers for the two numeric label fields, plus the beverage-type rules that depend on them.

The same parser runs on the application value and on the OCR text, so "45% Alc./Vol. (90 Proof)"
in the application and "45% ALC/VOL" on the label compare as numbers, not strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import BeverageType

from .normalize import fold, fold_digits

_NUM = r"(\d{1,3}(?:[.,]\d{1,3})?)"


def _to_float(num: str) -> float:
    """'13,5' -> 13.5 ; '1,750' -> 1750 ; '0.75' -> 0.75"""
    if "," in num and "." not in num:
        head, tail = num.split(",", 1)
        if len(tail) == 3 and head.isdigit():
            return float(head + tail)
        return float(head + "." + tail)
    return float(num.replace(",", ""))


# ----------------------------------------------------------------------------- alcohol content
@dataclass(frozen=True)
class Alcohol:
    percent: float | None
    proof: float | None
    raw: str

    @property
    def consistent(self) -> bool | None:
        """True when both percent and proof are present and agree (proof = 2 x percent)."""
        if self.percent is None or self.proof is None:
            return None
        return abs(self.proof - 2 * self.percent) <= 0.2


_ABV_PATTERNS = [
    # 45% Alc./Vol.   5.2% ALC/VOL   14.1% Alc. by Vol.   45 % abv
    re.compile(_NUM + r"\s*%\s*(?:alc|alcohol|abv|vol)", re.I),
    # Alc. 40% by Vol.   ABV 5.2%   Alcohol 13.5%   ALC 13.5% VOL
    re.compile(r"(?:alc(?:ohol)?\.?|abv)[\s.:]*" + _NUM + r"\s*%", re.I),
    # Alcohol 13.5 percent by volume / alc 13.5 by vol (no % sign)
    re.compile(r"(?:alc(?:ohol)?\.?)[\s.:]*" + _NUM + r"\s*(?:%|percent)?\s*(?:alc\.?\s*)?by\s*vol", re.I),
    # 13.5% by volume
    re.compile(_NUM + r"\s*%\s*(?:alc\.?\s*)?by\s*vol", re.I),
]
_PROOF = re.compile(r"(\d{2,3}(?:[.,]\d)?)\s*(?:°\s*)?proof", re.I)
_BARE = re.compile(r"^\s*" + _NUM + r"\s*%?\s*$")


def parse_alcohol(text: str, *, allow_bare: bool = False) -> Alcohol | None:
    """Extract alcohol content. ``allow_bare`` accepts a lone number such as "45" (application input only)."""
    t = fold_digits(text)
    percent: float | None = None
    for pat in _ABV_PATTERNS:
        m = pat.search(t)
        if m:
            val = _to_float(m.group(1))
            if 0 < val <= 100:
                percent = val
                break
    proof: float | None = None
    pm = _PROOF.search(t)
    if pm:
        pv = _to_float(pm.group(1))
        if 0 < pv <= 200:
            proof = pv
    if percent is None and proof is not None:
        percent = round(proof / 2, 2)
    if percent is None and allow_bare:
        bm = _BARE.match(t)
        if bm:
            val = _to_float(bm.group(1))
            if 0 < val <= 100:
                percent = val
    if percent is None and proof is None:
        return None
    return Alcohol(percent=percent, proof=proof, raw=text.strip())


def alcohol_matches(app: Alcohol, label: Alcohol, *, tolerance: float = 0.05) -> bool:
    if app.percent is None or label.percent is None:
        return False
    return abs(app.percent - label.percent) <= tolerance


# ----------------------------------------------------------------------------- net contents
@dataclass(frozen=True)
class Volume:
    ml: float
    raw: str
    unit: str


_UNIT_ML: dict[str, float] = {
    "ml": 1.0,
    "milliliter": 1.0,
    "millilitre": 1.0,
    "cl": 10.0,
    "centiliter": 10.0,
    "centilitre": 10.0,
    "l": 1000.0,
    "liter": 1000.0,
    "litre": 1000.0,
    "ltr": 1000.0,
    "floz": 29.5735295625,
    "oz": 29.5735295625,
    "ounce": 29.5735295625,
    "fluidounce": 29.5735295625,
    "pt": 473.176473,
    "pint": 473.176473,
    "qt": 946.352946,
    "quart": 946.352946,
    "gal": 3785.411784,
    "gallon": 3785.411784,
}
_NET = re.compile(
    r"(\d{1,4}(?:[.,]\d{1,3})?)\s*"
    r"(fl\.?\s*oz\.?|fluid\s*ounces?|ounces?|oz\.?|milliliters?|millilitres?|ml|"
    r"centiliters?|centilitres?|cl|liters?|litres?|ltr|l|pints?|pt\.?|quarts?|qt\.?|gallons?|gal\.?)"
    r"(?![a-z])",
    re.I,
)


def _unit_key(unit: str) -> str:
    u = re.sub(r"[^a-z]", "", unit.lower())
    if u.startswith("fl") and u.endswith("oz"):
        return "floz"
    if u.startswith("fluidounce"):
        return "fluidounce"
    for k in (
        "milliliter",
        "millilitre",
        "centiliter",
        "centilitre",
        "liter",
        "litre",
        "gallon",
        "quart",
        "pint",
        "ounce",
    ):
        if u.startswith(k):
            return k
    return u


def parse_volumes(text: str) -> list[Volume]:
    """All volume statements in the text, converted to mL. '12 FL OZ (355 mL)' yields two."""
    out: list[Volume] = []
    for m in _NET.finditer(fold_digits(text)):
        unit = _unit_key(m.group(2))
        if unit not in _UNIT_ML:
            continue
        ml = _to_float(m.group(1)) * _UNIT_ML[unit]
        if 0 < ml <= 60_000:
            out.append(Volume(ml=round(ml, 2), raw=m.group(0).strip(), unit=unit))
    return out


def volumes_match(app_ml: float, label_ml: float, *, tolerance: float = 0.01) -> bool:
    return abs(app_ml - label_ml) <= max(tolerance * app_ml, 0.5)


# ----------------------------------------------------------------------------- standards of fill
# 27 CFR 5.203(a) as amended Jan 10, 2025 and 4.72(a) as amended Jan 20, 2025 (docs/REGULATIONS.md).
SPIRITS_FILL_ML = (
    3750,
    3000,
    2000,
    1800,
    1750,
    1500,
    1000,
    945,
    900,
    750,
    720,
    710,
    700,
    570,
    500,
    475,
    375,
    355,
    350,
    331,
    250,
    200,
    187,
    100,
    50,
)
WINE_FILL_ML = (
    3000,
    2250,
    1800,
    1500,
    1000,
    750,
    720,
    700,
    620,
    600,
    568,
    550,
    500,
    473,
    375,
    360,
    355,
    330,
    300,
    250,
    200,
    187,
    180,
    100,
    50,
)


def is_standard_fill(beverage: BeverageType, ml: float) -> bool | None:
    """True/False for spirits and wine; None for malt beverages (no federal standards of fill)."""
    if beverage is BeverageType.malt:
        return None
    sizes = SPIRITS_FILL_ML if beverage is BeverageType.spirits else WINE_FILL_ML
    if any(abs(ml - s) <= max(0.005 * s, 0.5) for s in sizes):
        return True
    # 4.72(b): wine of 4 L and larger is allowed in even liters
    return beverage is BeverageType.wine and ml >= 4000 and abs(ml / 1000 - round(ml / 1000)) < 0.005


def fill_rule(beverage: BeverageType) -> str:
    return "27 CFR 5.203" if beverage is BeverageType.spirits else "27 CFR 4.72"


# ----------------------------------------------------------------------------- beverage rules
def alcohol_statement_required(beverage: BeverageType, class_type: str) -> tuple[bool, str]:
    """Whether a numeric alcohol statement is federally required, with the reason (simplified)."""
    if beverage is BeverageType.spirits:
        return True, "Required for distilled spirits (27 CFR 5.65)."
    if beverage is BeverageType.wine:
        ct = fold(class_type)
        if "table wine" in ct or "light wine" in ct:
            return False, "Wine of 7-14% may state 'Table Wine' or 'Light Wine' instead of a number (27 CFR 4.36)."
        return True, "Required for wine unless designated Table Wine or Light Wine (27 CFR 4.36)."
    return False, (
        "Optional for malt beverages under federal rules unless alcohol comes from added flavors "
        "(27 CFR 7.63, 7.65); state law may require it."
    )
