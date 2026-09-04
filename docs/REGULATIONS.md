# Regulatory basis for the checks

Verified 2026-09-03 against the eCFR versioner API (point-in-time 2026-08-29). The raw XML for
each section is saved next to this file under `regs/`. Where the app encodes a rule, this is
the source; where a rule cannot be checked from an image, it is listed as out of scope.

## Health warning statement: 27 CFR Part 16

**Text (16.21), verbatim:**

> GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic
> beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic
> beverages impairs your ability to drive a car or operate machinery, and may cause health
> problems.

16.21 also requires the statement to be "separate and apart from all other information", on the
brand label, a separate front label, or a back or side label.

**Format (16.22):**

| Rule | Regulatory language | Checked by the app |
|---|---|---|
| Anchor in capitals and bold | "The first two words ... 'GOVERNMENT WARNING,' shall appear in capital letters and in bold type." | Capitals: yes (from the OCR read). Bold: not in this build; shown as "Not checked" |
| Remainder not bold | "The remainder of the warning statement may not appear in bold type." | Not in this build; shown as "Not checked" |
| Letter case of the remainder | Not regulated: 16.22 requires capitals only for the two anchor words. On a sample of approved labels from the Public COLA Registry (`docs/EVAL_REAL.md`) most print the whole statement in capitals. | "Exact" compares the words character for character ignoring letter case and spacing; the anchor's capitals are the separate format check above |
| Legible, contrasting background | "readily legible under ordinary conditions, and ... on a contrasting background" | Not in this build |
| Not compressed | "shall not be compressed in such a manner that the warning statement is not readily legible" | No (needs physical measurement) |
| Minimum type size | 1 mm for containers of 237 mL or less; 2 mm for more than 237 mL up to 3 L; 3 mm for more than 3 L | Not in this build. Physical mm cannot be measured from an image without a known scale. |
| Max characters per inch | 40 at 1 mm, 25 at 2 mm, 12 at 3 mm | No (needs physical scale) |
| Firmly affixed | labels not removable without water or solvents | No (physical) |

Amendment history: T.D. ATF-294 (1990), T.D. 372 (1996), T.D. TTB-91 (2011).

Applicability: Part 16 applies to alcoholic beverages of 0.5 percent or more alcohol by volume
(27 CFR 16.10). When the application states less than 0.5 percent, the app reports the warning as
not required instead of missing.

## Standards of fill (authorized container sizes)

The app compares the parsed net contents to these lists and reports "Non-standard container size,
verify" when off-list. Never a failure on its own: the lists change (both were expanded by
T.D. TTB-200 in January 2025) and importers may have grandfathered stock.

**Distilled spirits, 27 CFR 5.203(a)** (T.D. TTB-200, 90 FR 1876, Jan. 10, 2025), 25 sizes:
3.75 L, 3 L, 2 L, 1.8 L, 1.75 L, 1.5 L, 1.00 L, 945 mL, 900 mL, 750 mL, 720 mL, 710 mL, 700 mL,
570 mL, 500 mL, 475 mL, 375 mL, 355 mL, 350 mL, 331 mL, 250 mL, 200 mL, 187 mL, 100 mL, 50 mL.
Exception 5.203(b): imported spirits in customs custody or bottled before Jan. 1, 1980.

**Wine, 27 CFR 4.72(a)** (last amended T.D. TTB-200, 90 FR 1875, Jan. 20, 2025), 25 sizes:
3 L, 2.25 L, 1.8 L, 1.5 L, 1 L, 750 mL, 720 mL, 700 mL, 620 mL, 600 mL, 568 mL, 550 mL, 500 mL,
473 mL, 375 mL, 360 mL, 355 mL, 330 mL, 300 mL, 250 mL, 200 mL, 187 mL, 180 mL, 100 mL, 50 mL.
4.72(b): containers of 4 L or larger are allowed in even liters (4, 5, 6 ...).

**Malt beverages (Part 7):** no standards of fill. The check is skipped for beer.

## Other mandatory label elements (context only)

Brand name, class/type designation, alcohol content, net contents, name and address of the
bottler or producer, and country of origin for imports come from 27 CFR Part 5 (spirits), Part 4
(wine) and Part 7 (malt beverages), and TTB's Beverage Alcohol Manuals. The app checks that
these match the application; it does not validate the designation itself, age statements,
name-and-address phrasing, alcohol-content statement wording, or laboratory tolerances
(5.65, 4.36, 7.65). Those are listed in LIMITS.md.

## Beverage-type differences the app encodes (simplified)

- Spirits: alcohol content required.
- Wine: alcohol content may be replaced by a "Table Wine" or "Light Wine" designation for
  7 to 14 percent wines. If the application provides a value, it is checked.
- Malt beverages: alcohol content optional under federal rules. If the application provides a
  value, it is checked.

## Sources

- eCFR API: `https://www.ecfr.gov/api/versioner/v1/full/2026-08-29/title-27.xml?part=<part>&section=<section>`
- Cornell LII mirror used for cross-reading: `https://www.law.cornell.edu/cfr/text/27/<section>`
- TTB labeling resources: `https://www.ttb.gov/regulated-commodities/beverage-alcohol/labeling`
