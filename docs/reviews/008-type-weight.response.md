1. **The estimator.**

   Sound enough as a same-line ranking heuristic above the gate, not as an absolute 3–8 px stroke-width measurement. The \(4\times\) identity is exact only for ideal parallel strips; real glyph topology and Otsu segmentation violate it (`app/pipeline/typeface.py:39-64`).

   - Thin strokes: biased high from pixel quantization; anti-aliasing and JPEG can move the Otsu boundary by a large fraction of the stroke.
   - Dense lowercase: counters and terminals bias low; junctions bias high. The net is text-dependent, usually lower than simple capitals.
   - Capitals: generally closer to the ideal-strip estimate and relatively high versus lowercase, creating a case/glyph-composition confound.
   - Textured ground: fine texture usually biases low by adding many one-pixel “ink” samples; broad dark texture biases high. The direction is uncontrolled once the minority-class assumption missegments the ground (`app/pipeline/typeface.py:47-58`).

   Do not switch immediately. Robustness per engineering hour:

   1. Current distance transform, with split/validity fixes.
   2. Ink area ÷ skeleton length, after removing small components; best alternative to shadow-test.
   3. Morphological-opening granulometry; simple but scale-quantized and structuring-element dependent.
   4. Stroke-width transform; potentially sounder, but costly and sensitive to weak/JPEG-corrupted gradients.
   5. Horizontal-run mode; cheapest but confounds glyph width, horizontal bars, orientation, and counters.

   The present bar tests validate only ideal strips, not those biases (`tests/unit/test_typeface.py:9-28`).

2. **The split (P3).**

   Prefer a semantic pixel boundary: find the connected-component/projection gap immediately after the printed colon, within a character-derived search window; use the stroke change point to score or refine candidate gaps. A free change-point optimizer always returns *something* when enough pixels exist—there is currently no “valid step” test (`split_experiment.py:57-78`). The all-bold sample’s spurious 0.13 split demonstrates this (`split_synth.log:6`).

   Require a positive left-to-right stroke drop, minimum ink on both sides, material SSE improvement/effect size, and ratio stability over nearby candidate splits. A character-share fallback may support Needs review, but must never produce a heading Match by itself.

   - `(1)` belongs wholly to the tail; otherwise its thin numeral can manufacture the transition.
   - Keep the colon in the heading, but exclude it with the margin.
   - Title case is fine empirically: 0.33 prior versus 0.37 pixel boundary (`split_synth.log:5`).
   - OCR-added/dropped characters damage only the prior; the pixel gap should remain authoritative.
   - A different face can create a stroke step without a weight change; treat that result as weaker evidence.
   - Two-line `GOVERNMENT` / `WARNING:` is currently located but cannot be weight-measured because the weight path requires both words on one line (`app/pipeline/warning.py:54-67`, `app/pipeline/warning.py:268-270`; `app/pipeline/typeface.py:26,96-106`). Measure both heading fragments and compare them with later body lines.
   - If only one body word follows the heading, the tail is too short; use compatible later body lines or abstain.

   The 0.8–1.6 prior window covers the observed synthetic boundaries, but clamp it to valid geometry and minimum segment content. A 0.15×type-height margin is a reasonable starting value; require at least one estimated stroke width and shrink it only when both resulting samples remain adequate (`split_experiment.py:140-148`).

3. **Geometry (P2).**

   The short **edge** of the raw OCR quadrilateral—not the short axis-aligned extent—is the type height for upright, 90°/270° retry, vertical-strip, and full-resolution-rescue reads. Compute opposing edge lengths or rectify the quad. The current min/max extents become wrong for skewed text, and the current x-axis split cannot handle a vertical line (`app/pipeline/typeface.py:87-105`; `app/pipeline/warning.py:75-91`). The malformed vertical cases in the experiment confirm this (`split_real.log:52,71,108`).

   Canonical stroke pixels should be `stroke_read / dec.scale`; that is geometrically scale-safe because canonical boxes use the same division (`app/pipeline/images.py:48-52,143-150`). Working-size versus rescue comparisons will still have rasterization error from Lanczos/Otsu, so validate tolerance rather than expect equality (`app/pipeline/images.py:111-115`, `app/services.py:254-264`). Using the unpadded box height as denominator corrects the present documentation/code mismatch, although padding can still alter which pixels enter the stroke estimate (`app/pipeline/typeface.py:67-74,90-94`).

   `_adopt` appends every rescued-span line and removes only kept-read lines overlapping those lines; non-overlapping kept lines remain (`app/services.py:229-246`). Thus the adopted span itself is single-read, but a later `find_warning` can form a hybrid span from rescued and retained lines. Preserve canonical stroke and type height per line—or pin the final span to one read—because `OcrLine` currently records neither source read nor scale (`app/schemas.py:64-74`).

4. **The matrix (P4–P6).**

   “Remainder not bold” cannot be asserted from this relative measurement. Extra-bold over bold is indistinguishable from bold over regular. P4’s `Not checked` is therefore correct; the current dual Match is unsafe (`app/pipeline/warning.py:303-310`).

   An absolute “body ratio below X means regular” gate is not defensible without broad, manually labelled font/weight calibration. Font design, capitalization, counters, box fit, Otsu, and resampling all move `stroke/type-height`. An unusually heavy body may justify Needs review, never Match or failure (`AGENTS.md:20-22`).

   P5’s ±25% size tolerance is too wide: an equal-weight heading 25% larger can generate a 1.25 stroke-pixel ratio and cross a 1.15 threshold solely from size. Require roughly ±10%, or normalize stroke by a validated type-height estimate. Real examples already combine 17–22% size differences with ratios of 1.33–1.39 (`split_real.log:7,84`).

   Provisionally use **1.20 for clearly heavier and retain 1.05 for same weight**, widening the inconclusive band to 1.05–1.20. After the corrected split, clean synthetic positives are 1.24–1.29, blurred positives only 1.16, and the sole all-bold negative is 1.00 (`split_synth.log:1-22`). Calling 1.16 Match leaves essentially no noise margin; do not raise the same-weight boundary until there are more all-bold, regular/regular, and bold/bold negatives.

5. **Validation.**

   D-045 must freeze the algorithm, corpus revision, font assets, thresholds, validity test, orientation handling, and exact denominators. Publish machine-readable rows, not only percentages.

   - Synthetic: counts and ratio distributions for regular/regular, bold/regular, bold/bold, extra-bold/bold, different faces, different sizes, title case, two-line headings, short tails, blur, JPEG, low contrast, scaling, and texture.
   - For every condition: eligible, measured, gap-split, change-point-split, fallback, rejected by each gate, Match, Needs review, and Not checked.
   - Report manual-boundary error, change-point effect/SSE improvement, raw and canonical stroke, type height, size ratio, head/body ratio, and classification.
   - Real: all 150 records and the 148 located warnings as counts; stratify same-line, standalone, split-heading, vertical, retry, rescue, measurable, and every abstention reason. Manually label a review subset for heading bold/body regular; approval alone is not pixel-level ground truth.
   - A false alarm is a bold-generated Needs review on a manually confirmed compliant approved label. Not checked is an abstention and must be reported separately. Also report unsafe false Matches on planted noncompliant labels.

   Honest summary: **“The heuristic detects a clear relative stroke increase in sufficiently large, comparable print and flags absence of that increase; it often abstains and cannot verify that the body itself is regular.”**

   Current evidence is inconsistent:

   - D-044 says 34 measurable/29 heavier/5 inconclusive/16 small, while `EVAL_REAL` reports about 64 heavier and 84 unmeasured-or-inconclusive among 148 located warnings (`docs/DECISIONS.md:D-044`; `docs/EVAL_REAL.md`, type-weight rows).
   - The real script is not the production pipeline: it performs one upright read, silently omits no-span images, and iterates images rather than records (`split_experiment.py:81-88,156-167`). Its log contains decode errors, vertical-axis failures, and a crop failure (`split_real.log:49,52,71,81,108,117`).
   - The synthetic log has 22 emitted rows—19 measurable and 3 too small—and no separately identified JPEG row, so the summarized category counts are not reproducible from that artifact (`split_synth.log:1-22`).
   - One all-bold negative is insufficient to validate either operating point.

6. **Tests.**

   Add these in order:

   - Bundled proportional regular/bold font: assert the recovered colon boundary and bold/regular ratio against known rendered coordinates.
   - Same proportional font, all bold: both rows Needs review; never a heading or body Match.
   - Extra-bold heading over bold body: heading may Match, body must remain Not checked.
   - Parameterized blur/JPEG/low-contrast/downscale tests for both bold/regular and all-bold.
   - Textured, gradient, inverted, and border-touching grounds: abstain rather than produce an unsafe Match.
   - `(1)` and the colon remain on opposite sides of the split.
   - OCR text with inserted/dropped characters but unchanged pixels yields the same pixel boundary/status.
   - Title-case heading and mixed-case body exercise glyph-composition bias.
   - Different heading/body faces cannot Match unless the configured evidence rule is satisfied.
   - `GOVERNMENT` / `WARNING: (1) ...` on two lines measures both heading fragments.
   - Heading plus only one body word uses later body lines or abstains.
   - Upright, 90°, 270°, and vertical-strip versions preserve short-edge height and classification.
   - Working-size and full-resolution rescue produce comparable canonical stroke values.
   - `_adopt` hybrid retained/rescued lines preserve per-line scale/source or are rejected.
   - Standalone-heading size tolerance tests just inside and outside its allowed range.
   - Padding and image-edge placement do not change the denominator.

   Existing tests use bars or inject ratios directly, so they do not exercise these paths (`tests/unit/test_typeface.py:44-55`; `tests/unit/test_warning.py:251-290`).

7. **Risks.**

   - **P5 can create new false Matches through size alone.** Tighten to about ±10% or normalize and validate.
   - **P3 can hallucinate a transition and its character fallback preserves the known defect.** Use colon-gap candidates, explicit step validity, minimum content, and prohibit fallback-derived Matches (`split_experiment.py:57-78`).
   - **P2 still fails vertical/skewed lines if implemented with min/max x/y.** Rectify the quadrilateral and operate along its long axis (`app/pipeline/typeface.py:87-105`).
   - **P1 can create unmeasured or mixed-read final spans and may retain large arrays longer.** Select and measure a read-local span before adoption; store canonical measurement provenance. It also remains synchronous while the OCR slot is held unless moved outside that scope (`app/services.py:162-168`).
   - **P4 reduces automatic coverage.** That is the correct tradeoff; ensure UI/verdict logic does not translate body `Not checked` into an implicit formatting Match.
   - **P6 at 1.15 becomes more permissive after removing tail contamination.** Use 1.20 provisionally and publish the wider abstention count.
   - **A failed change-point must not erase useful same-weight evidence.** Use a reliable semantic gap when available; otherwise report Not checked rather than manufacturing a boundary.