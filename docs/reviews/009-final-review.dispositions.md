# Dispositions for review 009 (final whole-repository pass)

Each finding was verified against the code before anything changed. Confirmed defects were fixed
in the commit that carries these dispositions; the rest are recorded with the reason. Line numbers
in the response count from each file's header in the review bundle.

## 1. Bugs

| # | Finding | Disposition |
|---|---|---|
| 1 | Single screen snapshots the files after the request returns | **Accepted.** `runCheck` snapshots the list before the request and carries a run number; a run superseded by Start over or another check is dropped when it returns. Wall time is now measured at the response, before the crops and the rendering. |
| 2 | Replacing batch images with the same names reuses old OCR | **Accepted.** The extraction cache is keyed by path, size and modification date; Remove all images clears it. |
| 3 | Assigning an image to an application keeps its old result and decision | **Accepted.** The assignment clears the result, the error and the decision, and announces that the decision was cleared. |
| 4 | Duplicate application references share one key | **Accepted.** A repeated reference is suffixed with its row number. |
| 5 | An unreadable alcohol value in the application counts as no value | **Accepted.** A value the tool cannot read as a percentage or a proof is Needs review with the value and the label's reading in the note (`tests/unit/test_review_009_fixes.py`). |
| 6 | Contradictory numbers can pass | **Partially accepted.** Two different percentages across lines are now Needs review even when the application gives no value. Two percentages inside one OCR line, and a net contents statement contradicted elsewhere on the label, are left as they are: not seen on the 150 real labels, and the crop is shown. |
| 7 | "Bottled in Napa, CA" against an Italian application is a Mismatch | **Accepted.** A state name or code counts as the United States for a match against a domestic application, not as a named country for a Mismatch; the line goes to the person. The existing test used "Napa Valley" and missed this; the new test uses the reviewer's example. |
| 8 | A two-line heading can pass bold; the caps check reads the second line's body | **Deferred.** A heading read on two lines is "not measured" in practice (D-047 counts it among the review reasons); a regular GOVERNMENT above a bold WARNING was not seen in any corpus. Noted in the decision log as a known gap. |
| 9 | Notes can be lost during batch processing; committing a note rebuilds the controls under a click | **Accepted.** A note-only change no longer rebuilds the table or the single screen's controls; a rebuild during a run carries the note being typed, its caret and the focus across. |
| 10 | Overlapping batch runs | **Accepted.** `start` refuses re-entry while a run is starting or running; the demo button is disabled during a run. |
| 11 | Unexpected health or compare JSON | **Accepted.** A health body without a usable worker count falls back to two; an empty compare result is an item error with a Resume hint rather than an "extract only" export. |
| 12 | Missing CSV-listed images do not qualify Ready | **Partially accepted.** The export's "what to look at" column now lists images that were listed but not uploaded; the verdict stays the server's, and the row already shows the missing names. |
| 13 | Proof column semantics; unknown imported values; oversized CSV cell | **Partially accepted.** A bare number under a Proof header becomes "N proof"; the csv field limit is raised so an oversized cell is a per-row error, not a 500. Unknown values in the imported column stay false (the template documents yes/no). |
| 14 | Numeric regexes read the tail of a longer number | **Accepted.** A number never starts inside another number ("17500 mL" is no longer 7500; "1045%" is no longer 45%). Decimal-comma volumes stay unsupported (they land in Needs review). |
| 15 | Transparent artwork turns black; coordinate rounding | **Partially accepted.** Transparent images are composited on white before conversion (test added). The rounding remark concerns strips a few pixels wide and is left. |
| 16 | Aborted batch work outlives its item | **Rejected.** The extraction cache is keyed per file, so a sibling read that finishes late only fills the cache; nothing it writes reaches the table. |
| 17 | Batch ETA divides by concurrency twice; "sending and receiving" includes rendering | **Accepted.** Both fixed. |
| 18 | Address corroboration accepts substrings | **Rejected for this build.** "Orange, NJ" inside "East Orange, NJ" corroborates the same state and a containing city name; the registered name must still match whole. Left as is. |

## 2. The assignment, item by item
Recorded as the reviewer's reading. The two-user latency overrun is stated in the README; the batch
scale run is 150 applications and 300 images, and the README says so. No change.

## 3. Setup and run instructions
| # | Finding | Disposition |
|---|---|---|
| 1 | `--network none` makes the published port unreachable | **Accepted.** The browser recipe runs with ordinary networking; `--network none` stays with the in-container smoke. |
| 2, 3 | Bare `pytest`, `ruff`, `mypy` after a `.venv/bin/pip` install; Windows paths | **Accepted.** The README activates the environment first and gives both shells. |
| 4 | Playwright setup absent | **Accepted.** The README points to `tests/browser/README.md`. |
| 5 | Baseline wording | **Accepted in part.** The README says the package index is needed at install time and that the models are in the repository. |
| 6, 7 | Manifests absent from the bundle; fixture regeneration depends on system fonts | **Noted.** Both manifests are in the repository (excluded from the bundle for size). The README says the label generator depends on system fonts. |

## 4. Documentation accuracy
| # | Finding | Disposition |
|---|---|---|
| 1 | Usability evidence still claimed in the trace | **Accepted.** Removed. |
| 2 | "Submitted build" provenance; 315 s against 495 s | **Accepted.** The rows name the build they were measured on, and the batch row cites both runs consistently. |
| 3 | Local latency 2.7 / 3.1 against EVAL's 2.458 / 2.955; real warning percentages | **Accepted.** The row cites EVAL's figures; the real-label percentages are restated from EVAL_REAL's counts. |
| 4 | "Every batch image exactly once" | **Accepted.** Reworded: one read per image plus the orientation retry when the first read is poor; no rescue round. |
| 5 | LIMITS describes an origin fix the code did not implement | **Accepted.** The code now does what LIMITS says (item 1.7). |
| 6 | Physical size "shown as Not checked" | **Accepted.** APPROACH and the About page describe physical size as outside the report. |
| 7 | EVAL's warning table puts wording issues under Needs review | **Accepted.** The evaluator records the assessment and counts wording with the issues; EVAL.md regenerated. |
| 8 | Exactness prose omits hyphen repair and the single-character exception | **Accepted.** One clause added to the README. |
| 9 | Accessibility claims exceed the tests | **Accepted in part.** "Every status" becomes "results"; the smokes are described as what they are. |
| 10 | SECURITY wording | **Accepted.** "Nothing sensitive is logged" narrowed to what is logged; "cross-origin isolation" becomes the two headers set; the memory bound names the request cap. |
| 11 | Config comment (first vs last XFF hop); agency branding unwired; trace link; AGENTS path | **Accepted.** Comment fixed; the agency-name row is removed from the README table; the link and the paths corrected. |
| 12 | Test count off by one | **Accepted.** 208 fast tests plus the 14 added here. |

## 5. User experience and error handling
| # | Finding | Disposition |
|---|---|---|
| 1 | Recovery controls during work | **Accepted.** Start over discards an in-flight result; the demo button is disabled during a run. |
| 2 | Sample failure paths | **Accepted.** Sample and demo loads check the HTTP status and report a failure; a click before the sample list arrives waits for it. |
| 3 | Framework errors without the envelope | **Accepted.** The handler is registered for Starlette's base exception, and the client reads a bare `detail` when no message is present. |
| 4 | Compare and CSV do not retry on 429 | **Deferred.** Compare is fast and runs outside the extraction slots; on the deployed two-worker host no 429 was seen on it in 300-image runs. |
| 5 | Null error JSON; request id; startup status | **Accepted.** A null or non-object body is treated as empty; the request id is appended to 500 messages; the start-up status polls until the engine is warm. A cancel control for a hanging single request is deferred. |
| 6 | Batch silently rejects files; unmapped columns hidden | **Accepted.** Skipped files are named with the reason; unused columns are listed under the spreadsheet. |
| 7 | Skip link changes the view; Details toggle loses focus | **Accepted.** An in-page anchor no longer routes; the Details button keeps the focus after the rebuild. |
| 8 | Verdict wording; "on-device" | **Accepted in part.** The About page says the model runs inside the service; the verdict sentences are unchanged. |
| 9 | TIFF previews; missing crops | **Deferred.** Browsers do not render TIFF; the verdict and the OCR lines still show. |
| 10 | Reduced motion | **Accepted.** The result scroll respects the preference. |

## 6. Security and privacy
| # | Finding | Disposition |
|---|---|---|
| 1 | `/compare` runs on the event loop | **Accepted.** The comparison runs in a worker thread; health stays responsive. |
| 2 | Oversized parts spool to disk | **Accepted.** The spool threshold sits above the request cap, which is enforced from Content-Length before the body is read, so no upload touches the filesystem. |
| 3 | Exception logging; access log | **Accepted in wording.** SECURITY.md states what the logs hold. |
| 4 | Deployment qualifications | **Noted.** SECURITY.md already conditions the proxy identity on the ingress. |
| 5-7 | CSV guard, headers, no secrets | Confirmations; no change. |

## 7. Code quality
| # | Finding | Disposition |
|---|---|---|
| 1 | Browser state ownership | **Accepted** through the fixes above (run number, snapshot, cache identity, re-entry guard). |
| 2 | Load tools count attempts | **Deferred.** The cited runs had zero failures, printed per run. |
| 3 | Typeface fallback selects the largest fluctuation | **Deferred.** The calibration (no approved label flagged, the planted all-bold defect caught) stands; noted with item 1.8. |
| 4 | `ocr_eval2.py` ignores `--max-side` | **Deferred.** A bake-off tool, not in the product path. |
| 5, 6 | Evaluation provenance; fetcher | **Deferred.** As in reviews 005 and 007. |
| 7 | jinja2 unused; agency name unwired; dead CSS; duplicated maps | **Accepted in part.** jinja2 removed from the requirements and the notices; the dead rule removed; the agency-name setting stays (a documented deployment slot) but leaves the README table. |

## 8. Tests
Unit tests added for items 1.5, 1.6, 1.7, 1.13, 1.14 and 1.15 (`tests/unit/test_review_009_fixes.py`).
Browser smokes now check that skipped batch files are named and that the skip link keeps the view.
The remaining suggestions (stale-response rejection through the browser, the full client error
matrix, service stress) are recorded as future work.

## 9. Ship list
Followed, with the deferrals above. The strongest and weakest points are quoted in D-048.
