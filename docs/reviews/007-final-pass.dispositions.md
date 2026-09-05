# Dispositions for review 007 (final pass over everything after review 005)

Each finding in `007-final-pass.response.md` was checked against the code before anything was
changed. Verdicts: **Accepted** (fixed as stated), **Partially** (fixed differently or in part, with
the reason), **Rejected** (with the reason), **Deferred** (true, not for this submission). The
fixing commit is the one that adds this file; the product decisions it records are D-045. The
bold-type items were taken further in consult 008 (`008-type-weight.*`), whose dispositions are
next to it.

## 1. Bugs introduced by these changes

| # | Finding | Disposition |
|---|---|---|
| 1.1 | Standalone-heading weight wrong for rotated reads (canonical y-extent is the line's length) | **Accepted.** The detector's quadrilateral is rectified before measuring (`typeface.rectify`), the type height is the box's short edge, and every measured line carries its stroke and type height in canonical pixels (`OcrLine.stroke_px`, `type_px`), so the standalone comparison no longer touches the canonical box's extents at all. Pinned by `test_rotated_and_vertical_lines_measure_like_the_upright_one`. |
| 1.2 | A heavier heading made both "heading bold" and "remainder not bold" Match | **Accepted.** A heading clearly heavier is a Match on the heading row only; the body row is Not checked with the note that a relative measurement cannot tell a regular body under a bold heading from a bold body under a heavier one. The all-bold case (same weight) stays Needs review on both rows. `type_weight_status`; pinned by `test_type_weight_bold_heading_over_regular_body_matches_the_heading_row_only`; the integration expectation on the clean sample changed accordingly. |
| 1.3 | Bottler containment was a raw substring test; city and state accepted anywhere on the label | **Accepted.** The registered name must appear whole at word boundaries in the folded line (`ACE` no longer matches `PALACE`), and the city and state must be read in the responsibility block: the found line and its neighbours in reading order on the same image (two before, three after), not the whole label (`_near`). Pinned by `test_bottler_name_inside_another_word_is_not_a_match` and `test_bottler_address_must_be_read_next_to_the_bottler_line`. |
| 1.4 | Any prefixed line ("Bottled in Napa, CA") counted as proof of another country | **Accepted.** A new `app/pipeline/countries.py` names the country a statement refers to (the world's countries, common aliases, U.S. forms and state names; "Georgia" is the state after a comma and the country on its own). An origin Mismatch now needs a recognised country other than the application's; the same country in another form is a Match; a place the tool cannot match is Needs review with the line shown. `test_countries.py`. |
| 1.5 | A failed second check left the previous result and decision on screen; export mixed old result with the live file list | **Accepted.** A check clears the previous result, decision and export at its start and hides the results; the files are snapshotted at check time and the export names those. `smoke_single.py` now fails a re-check on purpose and checks the screen is clear. |
| 1.6 | "Server-side latency" excluded multipart parsing and uploads | **Accepted.** `tools/loadtest.py` reads the `Server-Timing` header (the whole request on the server) and reports it as the server figure, with the response's own `timing.total_ms` beside it as the pipeline figure. The README's deployed rows are re-measured with it. |
| 1.7 | Percentile not nearest-rank | **Accepted.** `pct` is nearest-rank (the p95 of ten samples is the tenth). Pinned by `test_load_tool_percentile_is_nearest_rank`. Numbers re-measured. |
| 1.8 | Head/tail boundary from character count despite proportional glyph widths | **Accepted, and measured first.** On every bold-over-regular synthetic label the character-share boundary put 10-18 percent of the heading into the tail crop and pulled the ratio down by 0.07-0.09 (`008-type-weight.request.md`). The boundary is now the word gap in the print (a run of empty columns) near the character estimate, chosen by the largest stroke drop across it; without a gap the character share is a fallback that can support Needs review but never a Match. |
| 1.9 | Denominator was the padded crop height | **Accepted.** The ratio divides by the box's own type height; padding only supplies the surroundings. Pinned by `test_the_denominator_is_the_type_height_not_the_padded_crop`. |
| 1.10 | Table/light wine regex too broad ("Light Sparkling Wine") | **Accepted.** Only "table wine", "light wine", and those with a colour word ("table red wine", "red table wine", "light rosé wine") exempt the numeric statement. Pinned by `test_only_the_named_table_and_light_wine_designations_exempt_the_alcohol_statement`. |
| 1.11 | Warning card badge said Match with both bold rows at Needs review | **Accepted.** The badge is Needs review when any format row is. `render.js`. |
| 1.12 | Header-only CSV said "0 rows" | **Partially.** The spreadsheet summary now says "no data rows under the header"; the batch cannot start without usable rows, so the "0 of 0" line does not arise from this path. |
| 1.13 | Extract-only batch rows exported `done` as the verdict | **Accepted.** They export `extract_only`. |
| 1.14 | No wrong source array | Noted. The measurement now runs only on a located statement's lines, on the array of the read that produced them (`_measure_statement`). |

## 2. False passes and false alarms

| # | Finding | Disposition |
|---|---|---|
| 2.1 | ACE / PALACE with the address elsewhere | **Accepted** (1.3). |
| 2.2 | Extra-bold heading over bold body reaches Ready | **Accepted** (1.2): the body row is never a Match from this measurement. |
| 2.3 | "Light Sparkling Wine" exempted the alcohol statement | **Accepted** (1.10). |
| 2.4 | Wrong class becomes Needs review, never Ready | Noted. |
| 2.5 | `operate` read as `operated88 123` is noise | **Rejected.** The digits are stripped by the barcode rule and the remaining one-letter difference is the slip tolerance of D-038 (agreed in review 005): a person cannot tell a misprint from a small-print slip in an image, the diff names the word, and the row is Needs review, never Ready. |
| 2.6 | "Bottled in Napa, CA" against an Italian wine was an Issue | **Accepted** (1.4). |
| 2.7 | Net contents given but unread was an Issue, against rule 4 | **Accepted.** An unread net contents statement is Needs review with the application's value in the note, the same rule as an unread alcohol statement (D-041). Numeric disagreements stay issues. Pinned by `test_net_contents_given_but_not_read_is_review_not_an_issue`; LIMITS 14 updated. |
| 2.8 | "One Winery Road" not recognised as a street, so a name-only Match passed | **Accepted.** A token ending in a street word (road, street, avenue, way, drive, lane, highway, ...) is the street, and a line that ends city, state, ZIP without a recognisable street still yields the address. Pinned by `test_registered_street_without_a_number_and_a_line_ending_city_state_zip_still_yield_the_address`. |
| 2.9 | Blank net contents is D-040 | Noted. |
| 2.10 | Rule 4 not honoured by the origin branch and unread net contents | **Accepted** (1.4, 2.7). |
| 2.11 | Rule 3 honoured by the decision controls | Noted. |

## 3. Latency against the five-second requirement

| # | Finding | Disposition |
|---|---|---|
| 3.1, 3.2 | Every line of every read measured, on the event loop, while the slot is held | **Accepted.** The measurement runs only on the lines of a located statement (the engineer's direction: "detect bold where it is needed"), after `find_warning`, for the kept read and for a losing or rescue read only when a statement is found there. That is a handful of crops per image instead of every line; it stays synchronous. |
| 3.3 | Greyscale once; thread pin is process-global | Noted. |
| 3.4 | `ocr_ms` excludes the measurement; `total_ms` excludes parsing | **Partially.** The names are kept; the load tool and the README now say which figure is which (server header vs pipeline). |
| 3.5, 3.6 | Two-user wall p95 over five seconds on an earlier build; D-018's "under concurrent batch load" never measured | **Accepted as the measurement to run.** After deploying this commit the standard runs are repeated with the header figure and nearest-rank percentiles (`tools/measure_deployed.sh`), plus one run of the interactive path while a browser batch is in progress, and the README states what was measured, wall and server, one and two users. |
| 3.7 | `timing.total_ms` is not server-side latency | **Accepted** (1.6). |
| 3.8 | The 315-second browser batch belongs to the previous build | **Accepted.** Re-run on the deployed commit. |

## 4. Accessibility of the new UI

| # | Finding | Disposition |
|---|---|---|
| 4.1 | No dark text pair under 4.5:1 | Noted; confirmed by a computed-style audit of the live page in both themes (every text pair passes; the light footer line was 4.03:1 and is now `text-base-dark`). |
| 4.2 | Tile border, structural borders and the progress fill under 3:1 in dark | **Partially.** The theme tile border is `#8a9199` (5.2:1) and the dark progress fill `#8fc3ff` on its track (5.2:1). Table and card separators stay: they are decorative lines, not the boundary that identifies a control, and the light theme's own separators (`#dfe1e2` on white) are 1.3:1 as shipped by the design system. |
| 4.3 | Dark filter state lost; filters lack aria-pressed | **Accepted.** A dark rule for the pressed filter; `aria-pressed` on the filter buttons, kept current on click; the batch smoke checks it. |
| 4.4 | Dark rules override the forced-colors fill of pressed buttons | **Accepted.** A forced-colors rule after the dark block restores the system Highlight colours for pressed decision and filter buttons under the dark theme too. |
| 4.5 | Theme radios in forced colours depend on USWDS | Noted; the native radio input carries the state. |
| 4.6 | Recording a decision loses the focus and is not announced | **Accepted.** The rebuilt controls put the focus back on the same button (single screen and batch table), and a polite live region says "Decision recorded: Approve" / "Decision cleared". Both smokes check it. |
| 4.7 | Theme changes and view changes are not announced | **Partially.** Moving between pages now puts the focus on the new page's heading; the theme radios announce their own state, which is the native behaviour for a radio group. |
| 4.8 | Incremental batch progress not in a live region | Noted; the progress bar carries `aria-valuenow` and the status line announces start and completion. Unchanged. |
| 4.9 | Printing in dark mode; live controls printed | **Accepted.** The page switches to the light palette for printing and back afterwards (`theme.js`); the printout carries the decision and note as one static line and hides the buttons and the note field. |
| 4.10 | The accessibility statement overclaims | **Accepted.** Reworded to what is checked and by whom (browser tests: keyboard, 200 percent zoom, phone; contrast themes: by hand, by an author who uses one); decisions are announced; the progress bar's transition is off under reduced motion; filters expose their state. The single smoke now checks a 683-px viewport (200 percent on a 1366-px screen) for horizontal scrolling, and its first run found a real one: between 640 and 700 px the form's two columns hold the three beverage-type tiles, which could not shrink below their text and pushed the column past the viewport. The tiles now wrap and shrink (`.radio-row`); the claim was untrue until then. |

## 5. Security and privacy

| # | Finding | Disposition |
|---|---|---|
| 5.1 | Formula guard misses leading blanks or controls | **Accepted.** `csvCell` quotes a cell whose first non-blank, non-control character is `= + - @`. |
| 5.2 | Notes and OCR text safe in the DOM | Noted. |
| 5.3 | Object URLs never revoked | **Accepted.** Released a minute after the click. |
| 5.4 - 5.6 | localStorage, CSP, no new storage | Noted. SECURITY.md row updated to point at `render.js`. |

## 6. Docs accuracy

| # | Finding | Disposition |
|---|---|---|
| 6.1 | README placeholders | **Resolved (2026-09-04).** The usability clause is withdrawn (the row cites the browser tests); the personal section is replaced by a statement of the judgment calls. |
| 6.2 | Stale local latency row | **Accepted.** From the regenerated EVAL.md. |
| 6.3 | D-044's totals contradict EVAL_REAL; README mislabels non-Match as "too small" | **Accepted.** D-044's counts came from a 50-record calibration pass, not the corpus; D-045 records the corpus-wide counts per basis (heavier, same weight, inconclusive, too small, size differs, no heading), which the evaluator now emits as its own rows. README reworded. |
| 6.4 | REQUIREMENTS_TRACE said bold is not assessed | **Accepted.** |
| 6.5 | LIMITS and the config comment said 3.5 px | **Accepted.** 3.8 px everywhere. |
| 6.6 | The 146-row tally has no committed reproducer | **Accepted.** `tools/batch_tally.py` builds the spreadsheet from the registry export and runs the deployed batch screen; `tools/measure_deployed.sh` is the load-test sequence. |
| 6.7 | The 315-second browser batch is from the previous build | **Accepted** (3.8). |
| 6.8 | The 200 ms A/B claim is not backed by paired server-timing blocks | **Accepted.** LOADTEST says what was measured (wall time, same host, image swapped). |
| 6.9 | SECURITY points the formula guard at batch.js | **Accepted.** |
| 6.10 | evaluate_real.py header stale | **Accepted.** |
| 6.11 | D-043 overstates print as a record | **Accepted.** Reworded: the export is the record; the printout is a copy of the screen with the decision as one line. |
| 6.12 | "1 planted defects" | **Accepted.** |
| 6.13 | Otherwise consistent | Noted. |

## 7. Tests

| # | Finding | Disposition |
|---|---|---|
| 7.1 | Rotated standalone heading | **Accepted** (`test_rotated_and_vertical_lines_measure_like_the_upright_one`). |
| 7.2 | Bold body with extra-bold heading never matches the body row | **Accepted** (`test_type_weight_bold_heading_over_regular_body_matches_the_heading_row_only`). |
| 7.3 | Bottler substring and unrelated city | **Accepted.** |
| 7.4 | "Bottled in" a city is not contrary evidence | **Accepted** (`test_a_place_that_is_not_a_country_is_review_not_a_mismatch`). |
| 7.5 | Non-numeric light wine phrases | **Accepted.** |
| 7.6 | Barcode suffix hiding a word change | **Rejected** with 2.5. |
| 7.7 | Failed re-check clears the result | **Accepted** in `smoke_single.py`. |
| 7.8 | Focus, announcement, filter state, dark forced colours, dark printing | **Partially.** Focus retention, announcements and filter state are in the smokes; forced colours and printing are checked by hand. |
| 7.9 | Export semantics and hostile note prefixes | **Deferred.** There is no JavaScript unit runner in this build; the smoke checks the exported decision and note. |
| 7.10 | Nearest-rank percentile | **Accepted.** |
| 7.11 | Typeface tests with real proportional fonts | **Accepted.** Bold heading over regular body, all bold, all regular, and OCR text with dropped or added characters, set in Arial, DejaVu Sans or Liberation Sans when one is installed (skipped otherwise). |

## 8. Submission readiness

- (a) Placeholders: the engineer's. D-044's overclaims: corrected by D-045. The five-second framing: the README rows now cite the server header figure with the wall figure and the two-user figure beside it, measured on the submitted build. The tally and batch throughput: reproducers committed. The README narrative and the reviewers' section: left to the engineer, who wrote them in his voice. D-041's "address corroborates": now true of the code (1.3).
- (b) Nothing found; the stakeholder names and quotations are from the assignment's public repository; the engineer's identity and workflow are deliberate.
- (c) Every "must" item is done in this commit except the measurements, which follow the deploy; of the "can wait" items, measuring only the statement's lines, `extract_only`, and the header-only message are done; shortening the README narrative is the engineer's call.
