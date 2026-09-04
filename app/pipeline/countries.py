"""Country names for the origin check: which country, if any, a label's origin statement names.

A hard "origin mismatch" needs the label to name another country (D-041); "Bottled in Napa, CA"
names a place, not a country, and goes to the person (D-045). United States forms and state names
are recognised first, because they are the common case in the registry and a few state names are
also countries (Georgia).
"""

from __future__ import annotations

import re

from .normalize import _STATES, fold, key

# fmt: off
_COUNTRIES: tuple[str, ...] = (
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia",
    "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium",
    "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria",
    "Burkina Faso", "Burundi", "Cambodia", "Cameroon", "Canada", "Cape Verde", "Central African Republic", "Chad",
    "Chile", "China", "Colombia", "Comoros", "Congo", "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czech Republic",
    "Czechia", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador",
    "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon",
    "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana",
    "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy",
    "Ivory Coast", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait", "Kyrgyzstan",
    "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg",
    "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius",
    "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar",
    "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea",
    "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Panama", "Papua New Guinea", "Paraguay", "Peru",
    "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis",
    "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe",
    "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
    "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan",
    "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste",
    "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine",
    "United Arab Emirates", "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City",
    "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
)
# Other names a label prints, mapped to the name above. "Georgia" is both a country and a state:
# in an address it follows a comma ("Atlanta, Georgia") and counts as the United States; on its own
# ("Product of Georgia") it is the country.
_ALIASES: dict[str, str] = {
    "usa": "United States", "u s a": "United States", "us": "United States", "u s": "United States",
    "united states of america": "United States", "america": "United States", "american": "United States",
    "uk": "United Kingdom", "u k": "United Kingdom", "great britain": "United Kingdom", "britain": "United Kingdom",
    "england": "United Kingdom", "scotland": "United Kingdom", "wales": "United Kingdom",
    "northern ireland": "United Kingdom", "republic of ireland": "Ireland", "holland": "Netherlands",
    "the netherlands": "Netherlands", "republic of korea": "South Korea", "korea": "South Korea",
    "russian federation": "Russia", "czech": "Czech Republic", "cote d ivoire": "Ivory Coast",
    "cote divoire": "Ivory Coast", "burma": "Myanmar", "swaziland": "Eswatini", "macedonia": "North Macedonia",
    "republic of georgia": "Georgia", "east timor": "Timor-Leste", "turkiye": "Turkey",
    "bosnia": "Bosnia and Herzegovina", "trinidad": "Trinidad and Tobago", "prc": "China",
    "people s republic of china": "China", "republic of china": "Taiwan", "viet nam": "Vietnam",
    "brasil": "Brazil", "deutschland": "Germany", "espana": "Spain", "italia": "Italy", "mexique": "Mexico",
    "canadian": "Canada", "french": "France", "italian": "Italy", "spanish": "Spain", "german": "Germany",
    "mexican": "Mexico", "irish": "Ireland", "scotch": "United Kingdom", "japanese": "Japan",
    "australian": "Australia", "chilean": "Chile", "argentine": "Argentina", "argentinian": "Argentina",
    "portuguese": "Portugal", "greek": "Greece", "austrian": "Austria", "swiss": "Switzerland",
    "dutch": "Netherlands", "belgian": "Belgium", "polish": "Poland", "russian": "Russia",
    "south african": "South Africa", "new zealander": "New Zealand", "peruvian": "Peru",
    "jamaican": "Jamaica", "cuban": "Cuba", "dominican": "Dominican Republic", "puerto rico": "United States",
}
# fmt: on

_BY_FOLD: dict[str, str] = {key(name): name for name in _COUNTRIES} | {key(a): c for a, c in _ALIASES.items()}
# longest first, so "papua new guinea" wins over "guinea" and "dominican republic" over "dominica"
_ORDER = sorted(_BY_FOLD, key=len, reverse=True)
_STATE_NAMES = sorted((name for name in _STATES.values() if name != "georgia"), key=len, reverse=True)
_STATE_CODE = re.compile(r"(?:,|\b)\s*(" + "|".join(sorted(_STATES)) + r")(?:\s+\d{5}(?:-\d{4})?)?\s*\.?$")


def country_named(text: str) -> str | None:
    """The country a piece of label or application text names, or None. United States forms and
    U.S. state names (and a trailing state code such as ", CA") count as the United States."""
    f, k = fold(text), key(text)  # fold keeps punctuation (the comma test); key keeps letters and digits only
    if not k:
        return None
    if re.search(r"republic of georgia(?![a-z])", k):
        return "Georgia"
    if re.search(r",\s*georgia(?![a-z])", f):  # an address: "Atlanta, Georgia"
        return "United States"
    for state in _STATE_NAMES:
        if re.search(rf"(?<![a-z]){state}(?![a-z])", k):
            return "United States"
    if _STATE_CODE.search(text.strip()):
        return "United States"
    for name in _ORDER:
        if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", k):
            return _BY_FOLD[name]
    return None
