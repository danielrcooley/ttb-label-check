1. **Bugs introduced by these changes**

   1. **High:** Standalone-heading weight is wrong for rotated reads. Weight is measured against the raw horizontal box, but `type_weight_ratio` reconstructs pixels using the canonical box’s y-extent; for a rotated read that is the line’s length, not type height. Ratios therefore depend on character count and can falsely Match or review. `app/services.py:73-82`, `app/pipeline/warning.py:274-283`
   2. **High:** A heavier heading causes both “heading bold” and “remainder not bold” to Match. Relative weight cannot prove the body is not bold: an extra-bold heading over a bold body passes and can produce Ready. `app/pipeline/warning.py:303-310`, `app/pipeline/compare.py:424-448`
   3. **High:** Bottler containment is a raw substring test. Registered `ACE` can Match `PALACE WINES`; city and state may independently appear anywhere on the label, including appellation or marketing text. `app/pipeline/compare.py:121-128`, `app/pipeline/compare.py:145-152`, `app/pipeline/compare.py:166-174`
   4. **High:** `_origin_check` treats any prefixed line, including `Bottled in Napa, CA`, as proof of another country and returns Mismatch when the expected country was unread. The regex does not establish that the suffix is a country. `app/pipeline/compare.py:50-53`, `app/pipeline/compare.py:98-107`
   5. **High:** A failed second check leaves the previous result and decision visible. Export then combines the old application/result with the current mutable file list. Files are not snapshotted at successful check time. `app/static/app.js:71-92`, `app/static/app.js:170-193`, `app/static/app.js:199-209`, `app/static/app.js:226-231`
   6. **Medium:** The reported “server-side latency” excludes multipart parsing, upload reads and validation because service timing starts after those operations. The middleware’s `Server-Timing` covers the whole server request, but the load tool ignores it. `app/routes/api.py:119-122`, `app/services.py:291-301`, `app/security.py:131-195`, `tools/loadtest.py:68-74`
   7. **Medium:** The load-test percentile is not nearest-rank. For ten samples, p95 selects the ninth value instead of the maximum; the published 3,917 ms front-only p95 should be 3,928 ms under nearest-rank. `tools/loadtest.py:42-46`, `docs/LOADTEST.md:173-177`
   8. **Medium:** Same-line head/tail boundaries are inferred from character count, despite proportional glyph widths, prefixes and OCR spacing. Uniform all-bold text can be split across dissimilar glyph populations and exceed 1.15 spuriously. Uncertain without a pixel corpus. `app/pipeline/typeface.py:96-106`
   9. **Medium:** The documented denominator is the unpadded box height, but `_crop` adds padding and `stroke_ratio` divides by the padded crop height. At an image edge, clamping also removes the protective padding and can inflate border-touching strokes. `app/pipeline/typeface.py:44-64`, `app/pipeline/typeface.py:67-74`, `app/pipeline/typeface.py:90-94`
   10. **Medium:** The table/light-wine regex is broader than the decided red/white variants. `Light Sparkling Wine` or `Light Dessert Wine` is treated as the numeric-alcohol exception. `app/pipeline/parsers.py:57-58`, `app/pipeline/parsers.py:252-262`
   11. **Medium:** The warning card’s overall badge says Match whenever wording is exact and caps match, even when both bold rows are Needs review. The page therefore presents contradictory statuses. `app/static/render.js:122-145`
   12. **Low:** A header-only CSV produces “0 rows” and later “0 of 0 have problems,” rather than “no data rows.” `app/static/batch.js:65-72`, `app/static/batch.js:242-245`
   13. **Low:** Extract-only batch rows export `done` in the `verdict` column despite having no comparison result. `app/static/batch.js:199-206`, `app/static/batch.js:436-441`, `app/static/render.js:293-300`
   14. No wrong source array was found: chosen, losing-rotation and rescue lines are measured on their corresponding OCR arrays; weights survive `_adopt` and batch remapping. `app/services.py:125-138`, `app/services.py:229-267`, `app/static/batch.js:177-185`

2. **False passes and false alarms**

   1. **False Ready:** Application bottler `ACE WINES, Napa, CA`; label `BOTTLED BY PALACE WINES`, plus unrelated `Napa Valley` and `California` lines. Substring promotion plus global address search yields Match. `app/pipeline/compare.py:121-128`, `app/pipeline/compare.py:148-152`
   2. **False Ready:** Exact warning with bold body and extra-bold heading. Ratio ≥1.15 marks both format requirements Match although the body violates the rule. `app/pipeline/warning.py:303-310`
   3. **False Ready:** Wine class `Light Sparkling Wine`, no application or label ABV. The regex makes alcohol optional, returning Info; otherwise matching inputs may become Ready. `app/pipeline/parsers.py:258-262`, `app/pipeline/compare.py:229-252`
   4. **Not Ready, correctly:** A wrong class differing from the application becomes Needs review, never Ready. If the same invalid designation appears on both sides it Matches, but designation validity is explicitly out of scope. `app/pipeline/compare.py:384-406`, `docs/LIMITS.md:56-59`
   5. **Issue softened to review:** Canonical `operate` read as `operated88 123` satisfies the barcode rule because removing digits leaves a one-character “noise” change. A genuine wording change is hidden, although it still cannot become Ready. `app/pipeline/warning.py:228-246`
   6. **False Issue:** Expected `Italy`, label contains `Bottled in Napa, CA`, while the real origin is unread. This is classified as positive contrary-origin evidence. `app/pipeline/compare.py:98-107`
   7. **False Issue, pre-existing but now contradicted by new prose:** Application says `750 mL`, OCR reads no volume; net contents remains Not found and therefore Issues, although this is a heuristic read failure. `app/pipeline/compare.py:359-362`, `app/pipeline/compare.py:412-434`, `docs/LIMITS.md:105-113`
   8. A correct bottler using a spelled-out state is supported (`CA`/`California`). Less conventional streets such as `One Winery Road` are not recognized as addresses, allowing a name-only Match because `party.city` remains unset. `app/pipeline/normalize.py:207-221`, `app/pipeline/normalize.py:239-257`, `app/pipeline/compare.py:166-174`
   9. Blank net contents always causing Needs review is deliberate D-040, not an implementation false alarm. `app/pipeline/compare.py:306-323`
   10. AGENTS rule 4 is honored by the new class, unread-alcohol, blank-net and bold-review branches, but not by the overbroad contrary-origin branch; unread nonblank net contents also remains inconsistent with it. `AGENTS.md:18-19`, `app/pipeline/compare.py:98-107`
   11. AGENTS rule 3 is honored: Approve/Reject are explicitly user-recorded decisions, while the exported verdict remains the tool’s recommendation. `app/static/render.js:272-284`, `app/static/render.js:296-300`

3. **Latency against the five-second requirement**

   1. Weight processing runs synchronously on the event loop while the OCR slot remains held. Every line gets one distance transform; an anchor line can get three. Losing rotation reads and rescue reads are also measured. This can delay unrelated requests and health responses on text-dense images. `app/services.py:71-85`, `app/services.py:113-148`, `app/pipeline/typeface.py:47-64`
   2. Most work is unnecessary: construct lines first, locate the warning, then measure only its span. Batch currently pays the per-line cost for every extracted image so weights can later reach `/compare`. `app/services.py:137-138`, `app/services.py:170-171`, `app/static/batch.js:177-195`
   3. Greyscale is correctly computed once per read. `cv2.setNumThreads(1)` prevents OpenCV oversubscription, though it is process-global and also affects OCR preprocessing. `app/services.py:70-73`, `app/pipeline/typeface.py:22-24`
   4. `ocr_ms` stops before weight measurement, so its name now understates slot/CPU work; `total_ms` includes measurement but excludes route parsing and upload reads. `app/services.py:122-138`, `app/services.py:274-301`
   5. The documented worst deployed interactive result is over target: two clients had wall p95 6.028 s/max 8.882 s and server-service max 5.687 s. The real-label evaluation p95 is 7.462 s; rotated synthetic cases are about 6.566 s. `docs/LOADTEST.md:166-170`, `docs/EVAL_REAL.md:41-42`, `docs/EVAL.md:48`
   6. The acceptance decision requires deployed end-to-end p95 under concurrent batch load; no attached run measures that condition. Two interactive clients are not concurrent batch load. `docs/DECISIONS.md:26`, `docs/LOADTEST.md:159-185`
   7. The wall/server caveat is disclosed, but describing JSON `timing.total_ms` as server-side latency is incomplete. Use the middleware header or rename it “pipeline time.” `README.md:148`, `tools/loadtest.py:68-74`
   8. Current bold-build extract p95 supports approximately 1.92 s server pipeline time per image. The 315-second browser batch was measured on the preceding build, before D-044. `docs/LOADTEST.md:145-157`, `docs/LOADTEST.md:180-185`

4. **Accessibility of the new UI**

   1. No defined non-disabled dark-theme text/background pair appears below 4.5:1. The disabled `#71767a` on `#1a1f24` is about 3.6:1, but disabled controls are exempt. `app/static/app.css:161-195`
   2. UI contrasts below 3:1: tile border `#565c65` on `#1a1f24` ≈2.5:1; structural border `#3d4551` on `#1a1f24` ≈1.7:1 and on `#22282e` ≈1.5:1; progress fill `#005ea2` on track `#3d4551` ≈1.4:1. `app/static/app.css:190-191`, `app/static/app.css:199-224`, `app/static/app.css:105-106`
   3. Dark mode erases the active batch-filter styling: the later dark outline rule overrides the equally specific `.filter-bar .is-on` background. Filters also have neither a check mark nor `aria-pressed`. `app/static/app.css:114`, `app/static/app.css:193-195`, `app/static/batch.js:474-477`
   4. Forced-color decision buttons retain a check mark and explicit system-color outline. Dark-theme rules later override their forced-color fill with hard-coded colors; likely visible, but no longer honors the user’s palette. `app/static/app.css:140-148`, `app/static/app.css:226`
   5. Theme-radio forced-color behavior depends on vendored USWDS styles. Uncertain without the USWDS source. The custom dark rules provide no forced-color checked-state fallback. `app/static/app.css:190-192`
   6. Selecting a decision rebuilds and removes the focused button. Keyboard focus is lost, and no live region announces that the decision was recorded. `app/static/app.js:213-223`, `app/static/render.js:275-284`
   7. Theme radios remain focused and expose their native checked state, but nothing explicitly announces “Dark theme applied.” View changes likewise do not move focus to the newly shown page heading. `app/static/app.js:24-40`
   8. Results are announced through `role=status` and focus; batch start/done text is live. Incremental batch progress is not itself in a live region, although the progressbar value changes. `app/static/render.js:58-71`, `app/static/index.html:209-217`
   9. Printing in dark mode can produce near-white text on white paper when background printing is disabled. The print stylesheet does not force a light palette. It also prints live decision buttons/input rather than a static decision record. `app/static/app.css:151-164`, `app/static/app.css:181-232`
   10. The accessibility statement overclaims: decision selection is not announced, active filters are not semantically exposed, 200% zoom and contrast themes are not tested here, and the progress-bar width transition remains animated under reduced motion. `app/static/index.html:277-280`, `app/static/app.css:52`, `app/static/app.css:105-106`, `tests/browser/smoke_single.py:89-117`

5. **Security and privacy**

   1. CSV quoting, quote doubling, BOM and direct-prefix formula neutralization are correct. The guard does not handle leading spaces, LF or other controls before `= + - @`; note text is not trimmed. Risk depends on spreadsheet normalization. `app/static/render.js:303-312`
   2. Notes and OCR/user text remain safe in the DOM: controls use input values and all displayed text uses `textContent`; print does not introduce an HTML path. `app/static/render.js:21-36`, `app/static/render.js:275-284`
   3. CSV object URLs are never revoked, retaining exported application data and leaking memory until navigation. `app/static/render.js:310-315`
   4. `localStorage` contains only `labelcheck-theme`; labels, decisions and applications remain in memory. Logs contain method, path, status, timing and request ID only. `app/static/theme.js:4-26`, `app/security.py:197-205`
   5. `theme.js` is a same-origin external script and is permitted by the existing CSP; no inline-script exception was added. `app/static/index.html:10`, `app/security.py:24-27`
   6. No new server-side storage, cloud call or sensitive request parameter was introduced. `X-Batch` remains the only behavioral header. Client-supplied weight fields on `/compare` are trustable only as part of the already client-supplied OCR transcript. `app/routes/api.py:121-139`, `app/schemas.py:64-74`

6. **Docs accuracy**

   1. README still contains submission placeholders while claiming an observed usability test: `_USABILITY_RESULT_` and `_AUTHOR_SECTION_`. `README.md:40`, `README.md:224-226`
   2. README’s local latency row is stale: it says 2,536/3,059 ms; current EVAL says 2,524/2,922 ms. `README.md:145`, `docs/EVAL.md:9`
   3. D-044 says 150 labels produced 34 measurable, 29 heavier, 5 inconclusive and 16 too small. EVAL_REAL reports approximately 64 Match and 84 Not checked among 148 located warnings. README further mislabels every non-Match as “too small,” although the bucket includes inconclusive readings. `docs/DECISIONS.md:52`, `docs/EVAL_REAL.md:30-35`, `README.md:146`
   4. REQUIREMENTS_TRACE still says bold is not assessed automatically. `docs/REQUIREMENTS_TRACE.md:13`
   5. LIMITS says the stroke gate is 3.5 px; code and D-044 use 3.8 px. The config comment repeats the stale 3.5 value. `docs/LIMITS.md:41-43`, `app/pipeline/typeface.py:29`, `app/config.py:59-66`
   6. The 146-row deployed tally and 102 bottler matches have no committed reproducer or result artifact; the linked decisions/review record rationale, not the run. `README.md:147`, `docs/DECISIONS.md:48-49`
   7. The 315-second deployed browser batch belongs to build `a9738ed`, while README presents it beside current-build measurements. No post-D-044 browser batch is attached. `README.md:149`, `docs/LOADTEST.md:145-157`
   8. LOADTEST’s claimed 200 ms bold A/B is not represented by paired server-timing blocks; the prior build logged wall time only. `docs/LOADTEST.md:151-157`
   9. SECURITY points formula protection to `batch.js`; it now lives in shared `render.js`, and the stated protection omits its leading-whitespace limitation. `docs/SECURITY.md:43-45`, `app/static/render.js:303-306`
   10. `evaluate_real.py`’s header still describes applicant matching as `best_span/status_for` and lists a removed `case` warning assessment. `tools/evaluate_real.py:8-14`, `tools/evaluate_real.py:81-86`
   11. D-043 overstates print as a durable decision record; print renders live controls and is unsafe in dark mode. `docs/DECISIONS.md:51`, `app/static/app.css:151-164`
   12. EVAL’s “1 planted defects” is generated filler-level grammar. `docs/EVAL.md:64`, `tools/evaluate.py:199-203`
   13. D-040, blank-net behavior, class review-only behavior, new export headings, and moving Accessibility out of About are otherwise reflected consistently. `docs/DECISIONS.md:48-51`

7. **Tests**

   1. Add `test_rotated_standalone_heading_uses_raw_type_height`: rotated canonical strips must give the same weight verdict as their upright source. `app/pipeline/warning.py:274-283`
   2. Add `test_bold_body_with_extra_bold_heading_never_matches_body_not_bold`: prevent the principal D-044 false pass. `app/pipeline/warning.py:303-310`
   3. Add `test_bottler_substring_and_unrelated_city_do_not_match`: `ACE`/`PALACE`, with city/state elsewhere. `app/pipeline/compare.py:121-152`
   4. Add `test_bottled_in_city_is_not_contrary_country_evidence`: expected Italy plus `Bottled in Napa, CA` must not be Issues. `app/pipeline/compare.py:98-107`
   5. Add `test_non_numeric_light_wine_phrases_do_not_exempt_abv`: cover `Light Sparkling Wine` and `Light Dessert Wine`. `app/pipeline/parsers.py:258-262`
   6. Add `test_barcode_suffix_cannot_hide_word_change`: `operate` → `operated88 123` remains wording. `app/pipeline/warning.py:228-246`
   7. Add browser test `failed_recheck_clears_result_and_export_uses_checked_files`: pin stale-result and file-snapshot behavior. `app/static/app.js:170-231`
   8. Add browser accessibility test for retained focus, decision announcement, filter `aria-pressed`, dark forced colors and dark printing. `app/static/render.js:275-284`
   9. Add `test_export_error_extract_only_and_formula_cells`: pin semantic verdicts, bold columns and hostile note prefixes. `app/static/render.js:287-315`
   10. Add `test_loadtest_percentile_is_nearest_rank`: ten-sample p95 must be the tenth value. `tools/loadtest.py:42-46`
   11. Add typeface tests with real proportional fonts, antialiasing, border-touching glyphs, textured backgrounds and uniformly all-bold lines. Current bar tests do not exercise the estimator’s failure modes. `tests/unit/test_typeface.py:9-63`

8. **Submission readiness and ship list**

   1. **(a) Senior-reviewer markdown risks**
      - Unfilled placeholders and an unsupported “observed usability test” are immediate credibility failures. `README.md:40`, `README.md:224-226`
      - D-044 is overclaimed: wrong rotated geometry, unsupported body-not-bold inference, and contradictory calibration totals. `app/pipeline/warning.py:274-310`, `docs/DECISIONS.md:52`
      - The five-second claim is framed around partial pipeline timing while the actual two-user wall p95 exceeds five seconds; D-018’s concurrent-batch-load gate was not run. `README.md:39`, `docs/LOADTEST.md:166-170`, `docs/DECISIONS.md:26`
      - The 146-record tally and current batch throughput cannot be reproduced from committed artifacts. `README.md:147-149`
      - README’s long self-narrative and “for reviewers with a scoring sheet” section read as submission coaching rather than engineering evidence. `README.md:155-186`, `README.md:192-201`
      - D-041 says address corroborates the name, but code accepts city and state anywhere; the 70% applicant-match claim is therefore weaker than described. `docs/DECISIONS.md:49`, `app/pipeline/compare.py:121-128`

   2. **(b) Public-repository check**
      - No credential, local filesystem path, private registry artwork or private result row appears in the attached material. Real TTB IDs are explicitly public and artwork is not reproduced. `docs/EVAL_REAL.md:55-70`
      - Confirm permission to publish stakeholder names and verbatim take-home quotations; those are the only potentially non-owned material visible. `README.md:32-42`, `docs/REQUIREMENTS_TRACE.md:9-19`
      - The author’s full name, GitHub identity, domain and AI workflow are deliberate disclosures; remove only if not intentionally public. `README.md:7-10`, `README.md:217-222`

   3. **(c) Ship list**
      - **Must — L:** Make D-044 conservative: preserve raw type height/stroke pixels, stop inferring “body not bold” from relative heading weight, and test real proportional/rotated text.
      - **Must — M:** Fix bottler word-boundary matching, associate address evidence with the responsibility block, and handle nonnumeric/multiline street formats.
      - **Must — S:** Require an actual contrary country before origin Mismatch.
      - **Must — S:** Narrow the table/light-wine exemption.
      - **Must — S:** Clear stale results at check start and snapshot files/application/result for export and print.
      - **Must — M:** Use full `Server-Timing`, correct percentile calculation, rerun current-build interactive and browser-batch measurements, and align every published number.
      - **Must — M:** Fix dark filter state, focus retention/announcements, print colors, progress contrast and accessibility claims.
      - **Must — S:** Remove placeholders; update REQUIREMENTS_TRACE, LIMITS, SECURITY, D-044 totals and stale README latency.
      - **Must — S:** Harden CSV formula prefixes and revoke object URLs.
      - **Can wait — M:** Measure only warning-span lines and move pixel work off the event loop.
      - **Can wait — S:** Add bold statuses to explicit CSV columns and use `extract_only` instead of `done`.
      - **Can wait — S:** Improve header-only CSV messaging.
      - **Can wait — M:** Shorten the README narrative and scoring-sheet prose after factual blockers are fixed.