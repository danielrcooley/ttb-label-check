---
id: 008
type: design consult (method review of the bold-type measurement, D-044)
status: answered (response in 008-type-weight.response.md; dispositions in 008-type-weight.dispositions.md)
requested_by: Claude (builder), at the author's request ("review the bold detector and collaborate with Codex on it")
reviewer: Codex (reviewer)
date: 2026-09-04
inputs: the current text of app/pipeline/typeface.py, app/pipeline/warning.py, app/services.py, app/schemas.py, app/pipeline/images.py, the two test files, the decision and doc rows, the relevant findings of review 007, and the builder's measurement scripts with their output on both corpora (appended after this request)
---

# Consult 008: how to measure bold type in the warning statement

## What the product does today (D-044)
27 CFR 16.22(a)(2) requires "GOVERNMENT WARNING" in capitals and bold and the rest of the statement
not in bold. OCR gives text and boxes, not weight. The product measures each OCR line's stroke
thickness on the array the engine read: greyscale, Otsu, the minority class is ink, the L2
distance transform over the ink, stroke = 4 x the mean distance, divided by the crop height
(`stroke_ratio`). A line carrying the heading is measured as heading and remainder separately,
splitting the box at the heading's share of the CHARACTERS (`m.end() / len(text)`), the head
crop trimmed to 0.95 of that point and the tail crop starting at 1.08 of it (`measure_line`).
`type_weight_ratio` compares the heading with the rest of its own line, or, when the heading
stands alone, its stroke in pixels (weight x the canonical box's y-extent) with the median of the
other lines'. `type_weight_status`: ratio >= 1.15 gives Match on both format rows ("heading bold",
"remainder not bold"); <= 1.05 gives Needs review on both; between is inconclusive (Not checked);
too small or faint is Not checked with the reason. Gates: box height >= 24 px and stroke >= 3.8 px.
Every line of every read (upright, the rotation retry's losing reads, rescue reads) is measured.

## What review 007 found (verbatim numbering from that response)
- 1.1 High: for a rotated read the canonical box's y-extent is the line's LENGTH, not the type
  height, so the standalone-heading comparison is wrong there.
- 1.2 High: a heavier heading cannot prove the body is not bold (extra-bold over bold passes both
  rows and can reach Ready).
- 1.8 Medium: the head/tail boundary is inferred from character count despite proportional glyph
  widths; uniform all-bold text could be split across dissimilar glyph populations.
- 1.9 Medium: the documented denominator is the unpadded box height but the crop is padded by 2 px
  and clamped at image edges.
- 3.1/3.2: the measurement runs on the event loop while the OCR slot is held, for every line of
  every read, most of it unnecessary: locate the warning first, then measure only its span.
- 7.11: the tests draw bars; they do not exercise proportional fonts, anti-aliasing, edges,
  textured grounds or uniformly all-bold lines.

## What the builder measured (scripts and full output appended)
Experiment A, on every heading-carrying line of a located statement: the per-column stroke
profile of the line crop (4 x mean distance per column) and its single change point (the split
that minimizes the within-segment sum of squares, searched over 12-70 percent of the width),
against the product's character-share split. Synthetic corpus (bold heading over regular body,
Roboto-like faces; the all-bold planted defect; blur, low contrast, JPEG variants):

| label | product split | tail crop starts | pixel change point | share of the tail crop that is still heading | ratio, product split | ratio, pixel split |
|---|---|---|---|---|---|---|
| clean (8 labels) | 0.40 | 0.43 | 0.48-0.53 | 10-18 % | 1.17-1.21 | 1.24-1.29 |
| blur (3) | 0.40 | 0.43 | 0.49 | 11-12 % | 1.12-1.13 (inconclusive) | 1.16 |
| low contrast / JPEG / altered (5) | 0.40 | 0.43 | 0.48 | 10 % | 1.18-1.19 | 1.27-1.28 |
| title-case heading (1) | 0.33 | 0.36 | 0.37 | 2 % | 1.24 | 1.27 |
| all bold (1) | 0.47 | 0.51 | none (0.13, no step; columns 5.1 vs 5.2 px) | 0 | 0.99 | 1.00 |

Capitals set bold are wider than lowercase, so the heading's true share of the width exceeds its
share of the characters by about a quarter; the product's tail crop begins inside the bold heading
on every bold-over-regular label, which drags the ratio down by 0.07-0.09 and puts correct but
blurred labels in the inconclusive band. The real corpus (150 approved labels) is in the appended
`split_real.log`, one line per located statement, same columns; "B" lines are statements whose
heading stands alone, with the heading's box height against the median of the other lines'.

## The builder's proposed redesign, for your critique
P1. Measure only the lines of a located statement (after `find_warning`), on the array they were
    read from; the rotation retry's losing reads and rescue reads are measured only when a span is
    found in them. The author's direction: "just detect bold where it's needed".
P2. Geometry: the type height is the SHORT side of the box in the read's own array (a line is
    always longer than it is tall); the stroke is carried in canonical pixels (stroke in the read's
    pixels times the read-to-canonical scale), so the standalone-heading comparison is right for
    upright reads, rotated reads, a sideways strip boxed vertically in an upright read, and the
    full-resolution rescue read; the ratio's denominator is the unpadded box height.
P3. Split the heading line at the pixels: the change point of the per-column stroke profile,
    searched within 0.8 to 1.6 times the character-share estimate, with a margin of 0.15 x type
    height on each side of it; when no valid change point exists, fall back to the character share.
P4. Matrix: heading clearly heavier (>= threshold) gives "heading bold" = Match and "remainder not
    bold" = Not checked with the note "lighter than the heading; its own weight is not measured";
    same weight (<= threshold) gives Needs review on both rows with one note (either the heading is
    not bold or the whole statement is); between = inconclusive; unmeasured = Not checked with the
    reason. Never a failure.
P5. Standalone heading: compare canonical stroke pixels with the median of the body lines' only
    when the heading's type height is within 25 percent of the body's median type height; otherwise
    Not checked ("the heading is set in a different size; weight cannot be compared").
P6. Thresholds: keep 1.15 / 1.05 unless the new distributions say otherwise.

## What we need from you
Terse numbered answers, most important first, citing file and line into the attached material.
Where you are not sure, say so in five words and move on. Do not restate the code.

1. **The estimator.** Is 4 x mean distance transform over Otsu ink a sound stroke-width estimate
   for 3-8 px strokes with anti-aliasing and JPEG ringing? Name the bias direction for thin
   strokes, for dense lowercase (counters, junctions), for capitals, and for a textured ground.
   Is there a cheaper or sounder estimator worth switching to before submission (granulometry by
   morphological opening, the mode of horizontal run lengths, the stroke width transform, the
   ratio of ink area to skeleton length)? Rank by robustness per hour of work.
2. **The split (P3).** Change point on the column stroke profile versus finding the gap after the
   colon versus anything else; the failure modes you expect (the "(1)" numeral, the colon, a
   heading in title case, an OCR text that drops or adds characters, a heading in a different face,
   a statement whose heading is split over two lines "GOVERNMENT" / "WARNING: (1) ...", a heading
   line that is only "GOVERNMENT WARNING:" plus one word). Is the search window and margin right?
3. **Geometry (P2).** Confirm or correct that the short side of the read-array box is the type
   height in each of the four read cases, and that carrying the stroke in canonical pixels makes
   the standalone comparison scale-safe across a working-size read and a full-resolution rescue.
   Say what `_adopt` (a rescued statement replacing lines of the kept read) does to a span whose
   lines come from two reads.
4. **The matrix (P4, P5, P6).** Can "remainder not bold" ever be asserted from this measurement?
   Is an absolute gate on the body (stroke over type height at or below some value = regular
   weight) defensible at the working size, given the estimator's bias? Are 1.15 and 1.05 the right
   operating points after the split fix; if you would move them, to what and why; and should the
   inconclusive band be wider?
5. **Validation.** What must be reported for D-045, EVAL.md and EVAL_REAL.md so a reviewer can
   reproduce and believe the claim: which distributions, which counts per corpus, what counts as a
   false alarm on approved labels, and what the honest one-sentence summary of the method's power
   is. Point at anything in the appended output that contradicts the proposed numbers.
6. **Tests.** The tests to add, one line each, in the order you would write them; include at least
   one that draws proportional text with a real font rather than bars.
7. **Risks.** Anything in P1-P6 that makes the product worse than today, and the cheapest way to
   avoid it.

## Rules
Read-only; report only. Do not run commands or modify files. D-044 (measure bold from the pixels,
report it as a heuristic, never fail on it) is the author's decision; the question is how to do it
well. AGENTS.md rule 4 holds: heuristic findings are Needs review, never Fail.
