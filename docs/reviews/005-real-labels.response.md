1. **Bugs introduced**

   1.1 **Critical:** “Exact” deletes every space, so changed word boundaries pass: `women should` → `womens hould`, `a car` → `acar`. That can produce Ready for approval for text that is not word-for-word. `app/pipeline/warning.py:152-160`, `app/pipeline/compare.py:303-304`

   1.2 **High:** `fold_company` removes corporate tokens everywhere, including address data. Application `ACME LLC, Denver, CO` and label `ACME, Denver` both become `acme denver`; different entities such as `ACME LLC` and `ACME Inc.` also become identical and can pass. `app/pipeline/normalize.py:118-136`, `app/pipeline/compare.py:96-108`

   1.3 **High:** Rescue results depend on current load. It releases the original slots, reacquires one, and silently swallows `BusyError`; batch acquisition fails immediately under contention, while interactive acquisition can wait eight seconds and then silently omit the rescue. Identical input can therefore produce different verdicts, violating determinism. `app/services.py:132-146`, `app/services.py:166-201`, `app/ocr/pool.py:110-128`, `AGENTS.md:27-28`

   1.4 **High:** Rescue does not perform the promised search. The first 90°/270° span merely beating `floor` causes an immediate break, suppressing the other orientation and full-resolution read even if either would be exact. A mediocre first span can therefore remain a wording issue. `app/services.py:175-189`

   1.5 **High:** Any image whose general retry selected a rotation is excluded from rescue. The selected orientation is based on total confidence, not warning quality, so an exact warning in the discarded orientation can remain missed. `app/services.py:169-170`, `app/services.py:176-180`, `app/services.py:87-108`

   1.6 **Medium:** Rescue’s second slot wait is omitted from `queue_ms`; only total time remains correct. Per-image `ocr_ms` includes rescue execution but not rescue queuing. `app/services.py:167`, `app/services.py:199`, `app/services.py:208-213`

   1.7 **Medium:** Bottler evidence is reconstructed in original OCR-list order, not candidate reading order, and box equality can include duplicate lines sharing a box. Status remains based on the folded candidate while `found`, evidence, and “Label says” may show different text/order. `app/pipeline/compare.py:99-107`, `app/pipeline/match.py:119-133`

   1.8 **Medium:** Whole-image median thickness can merge nearby distinct columns or fail to merge a thin-text column when unrelated large/small text dominates the median. Sorting such a merged group top-to-bottom can scramble warning and generic-field spans. `app/pipeline/match.py:53-64`, `app/pipeline/match.py:68-83`

   1.9 **Low:** `group.index(head[-1])` finds the first value-equal OCR line, not necessarily the actual anchor line. Duplicate OCR records can restart accumulation from the wrong position. `app/pipeline/warning.py:99-107`

   1.10 Mixed-orientation boxes may still misjoin. `_column_overlap` chooses its axis independently for every pair and uses horizontal overlap whenever either box is not taller than wide. `app/pipeline/warning.py:72-83`

   1.11 No coordinate or slot leak found. Both working-size and high-resolution boxes use their own decode scale; cancellation during the sequential rescue keeps the slot until the shielded inference finishes. `app/services.py:177-199`, `app/services.py:50-57`, `app/ocr/pool.py:148-164`

2. **False passes and false alarms**

   2.1 **False Ready:** `GOVERNMENT WARNING: ... womens hould not drink ...` is “exact” because all spaces are removed. Case-insensitivity itself is supported for the body; 16.22 regulates capitals only for the anchor, which remains separately checked. `app/pipeline/warning.py:152-160`, `docs/REGULATIONS.md:21-29`

   2.2 **False Ready:** `ACME LLC, Denver, CO` versus `ACME, Denver`, or `ACME LLC` versus `ACME Inc.`, can be a bottler Match after folding. The displayed “Label says” note does not prevent Ready. `app/pipeline/normalize.py:126-136`, `app/pipeline/compare.py:97-107`, `app/pipeline/compare.py:294-304`

   2.3 **Wrongly softened issue, not Ready:** genuine `women` → `woman`, `your` → `yours`, or `risk` → `rusk` is classified as OCR noise and only Needs review. The hand-check confirms `WOMAN` was genuinely printed, so this is not merely hypothetical. `app/pipeline/warning.py:178-220`, `docs/EVAL_REAL.md:52`

   2.4 **Wrongly softened issue, not Ready:** inserting `2026` anywhere in the statement is always noise; a genuinely printed extra number no longer produces Issues. `app/pipeline/warning.py:211-219`

   2.5 **No threshold false Ready:** a genuinely different brand scoring 80–89 becomes Needs review, not Match. It can still improperly soften an Issues verdict; the recorded `GreatNation` score 86 demonstrates the band. `app/pipeline/match.py:149-153`, `docs/EVAL_REAL.md:59`

   2.6 **False alarm:** if OCR adds a trailing hyphen to a complete word—`during-` followed by `pregnancy`—the new join produces `duringpregnancy`, usually a wording issue rather than punctuation noise. `app/pipeline/normalize.py:104-115`

   2.7 **False alarm/miss:** a 90° partial span scoring above the upright floor suppresses an exact 270° or high-resolution result. `app/services.py:175-189`

   2.8 **False alarm:** nearby columns within an inflated tolerance can be interleaved top-to-bottom, turning a correct statement into reordered wording. `app/pipeline/match.py:60-83`

   2.9 The case decision drops no regulated body-case check: body case is not specified, and anchor capitals remain checked. Existing required bold, non-bold body, contrast, compression, and physical-size checks remain explicitly unimplemented. The product’s “exact” note is nevertheless untrue while arbitrary word-boundary changes pass. `docs/REGULATIONS.md:23-30`, `app/pipeline/warning.py:264-290`

3. **Latency against five seconds**

   3.1 One image costs 1 pass when the warning is usable; ordinary missing-warning images cost 3 passes (upright + 90° + 270°), or 4 when large. A readable image that already triggered both general rotations can cost 5 small-image or 6 large-image passes. At 2.0 s/pass: approximately 2, 6, 8, 10, or 12 seconds. `app/services.py:96-106`, `app/services.py:136-146`, `app/services.py:175-199`

   3.2 A front/back pair with usable warning costs 2 engine passes: approximately 2 seconds interactive because the images run together, approximately 4 seconds batch because they run serially. `app/services.py:124-135`

   3.3 A normal pair with no warning costs 6 passes when small and 8 when both are large. Current rescue is serial: approximately 10/14 seconds interactive and 12/16 seconds batch. Worst case is 12 passes: approximately 18 seconds interactive or 24 seconds batch. `app/services.py:132-145`, `app/services.py:167-199`

   3.4 Interactive queuing can add up to eight seconds before the original reads and another eight before rescue. The second wait is hidden from `queue_ms`. `app/config.py:69-71`, `app/ocr/pool.py:110-117`, `app/services.py:167`

   3.5 The likely evaluator cases all fail the target: front-only with no statement ≈6 seconds and is already an integration scenario; a genuinely missing pair ≈10 seconds and directly tests an emphasized requirement; a large upload ≈8–14 seconds and is plausible but less certain. `tests/integration/test_verify_api.py:140-145`, `docs/REQUIREMENTS_TRACE.md:9-12`

   3.6 If the browser continues sending one-image batch extracts, every front image lacking the back-label warning independently pays the rescue cost before pairing. That invalidates “each image is read once” and the recorded batch throughput. `README.md:72-74`, `app/routes/api.py:125-139`, `app/services.py:136-146`

   3.7 Cheapest mitigations, ranked:

   1. **S:** Disable automatic rescue and offer it as an explicit retry. Baseline latency returns; the documented sideways bourbon and high-resolution 3 L case remain Issues either way. Corpus impact is not knowable. `docs/EVAL_REAL.md:53-55`
   2. **S:** Disable rescue for batch/extract-only requests; retain it for interactive verification. This protects throughput but may lose evidence for vertical warnings in batch. `app/services.py:121-146`
   3. **S:** Remove the high-resolution pass. Its only documented case improved similarity from 0.23 to 0.90 but stayed Issues, so no documented verdict changes. `docs/EVAL_REAL.md:55`
   4. **M:** Add a cooperative 4.5-second/pass budget and stop launching new reads. This guarantees honest timing but may try only one orientation. `app/services.py:175-199`
   5. **M:** Run rescue reads across available slots. One image can approach four seconds; a two-image pair needing both orientations still approaches six seconds on two workers and increases contention. `app/config.py:30-33`, `app/services.py:167-199`
   6. **L/ops:** Four vCPUs/workers plus parallel rescue can keep a small missing pair near four seconds; high-resolution work still needs budgeting. No attached evaluation predicts accuracy at that sizing.

4. **Evaluation tooling and claims**

   4.1 `cola_fetch.py` does use one session, an identifying agent, and start-to-start delay. It does not close the session, validate a positive delay, or bound response bytes. `tools/cola_fetch.py:179-198`, `tools/cola_fetch.py:265-275`

   4.2 `--max-requests` is not a hard cap: search consumes three requests regardless of the setting, and the loop checks only before the form, after which up to `max-images` further requests run. `tools/cola_fetch.py:200-221`, `tools/cola_fetch.py:300-326`

   4.3 Resumption is incomplete: a failed image is permanently omitted once any image lets the row commit; a crash after image writes but before the CSV row causes refetch/overwrite; previous records from another date window or seed are silently mixed into the next report. `tools/cola_fetch.py:280-293`, `tools/cola_fetch.py:321-364`

   4.4 Default writes stay under `tests/fixtures/real`, but `--out` permits any path and registry-derived `ttbid` is not sanitized before filename construction. Thus confinement is not enforced. `tools/cola_fetch.py:274-279`, `tools/cola_fetch.py:306`, `tools/cola_fetch.py:334-335`

   4.5 Form/image failures are handled; search/export, malformed CSV columns, filesystem errors, and output generation abort the run. `tools/cola_fetch.py:291-308`, `tools/cola_fetch.py:313-339`

   4.6 Registry use is defensible as a small, public, rate-limited, aggregate-only evaluation, but the tool records no terms/robots review or provenance beyond the URL. Artwork is correctly kept out of the committed report. `tools/cola_fetch.py:2-17`, `docs/EVAL_REAL.md:3-13`

   4.7 Present, exact-of-present, match-or-review, origin denominators, and warning counts are coded as described; no aggregate double counting is evident. `tools/evaluate_real.py:214-246`, `tools/evaluate_real.py:252-256`

   4.8 “Warning present” is flattering: any fuzzy anchor span counts, with no minimum similarity or completeness threshold. `app/pipeline/warning.py:86-128`, `tools/evaluate_real.py:145-152`

   4.9 Origin is also flattering: any line partially matching a country at 90 qualifies, without origin wording; `GEORGIA PEACH` can satisfy imported origin `Georgia`. `tools/evaluate_real.py:140-144`

   4.10 Alcohol/net “read” rates mean any parse anywhere. Concatenating all lines and images can even synthesize a statement across unrelated line or image boundaries. `app/pipeline/extract.py:30-41`, `tools/evaluate_real.py:153-156`

   4.11 Latency excludes file loading and `_fit` resizing, and p95 uses a floor-indexed order statistic one rank below conventional nearest-rank p95. Both slightly flatter latency. `tools/evaluate_real.py:113-120`, `tools/evaluate_real.py:247-250`

   4.12 The aggregate correctly disclaims ground truth. The targeted hand-check cannot establish overall precision, and only one of the two absent records is shown as genuinely absent; it does not support README’s claim that both misses lacked a statement. `docs/EVAL_REAL.md:13`, `docs/EVAL_REAL.md:43-60`, `README.md:136`

5. **Docs accuracy**

   5.1 README’s deployed 3.1-second claim predates these rescue passes; the cited load test was run September 3, while the new path is unmeasured and can exceed five seconds. `README.md:38`, `docs/LOADTEST.md:65-69`, `app/services.py:136-199`

   5.2 README’s degraded results are stale: it says 16/20 exact, 15 Ready, three Issues and two sideways failures; current EVAL says 18/20, 17 Ready, one Issue and both rotated cases Ready. `README.md:133-144`, `docs/EVAL.md:36-49`

   5.3 README still says “character-level,” “literal,” and “character for character” without disclosing case/spacing removal; it also says each batch image is read once. `README.md:41`, `README.md:67-74`

   5.4 README’s test counts were not updated after adding these tests: it still advertises 107 unit and 16 integration tests. `README.md:114-119`, `tests/unit/test_services.py:78-140`, `tests/integration/test_verify_api.py:62-86`

   5.5 LIMITS claims both sideways reads and then full resolution for every eligible image; code stops after the first improving sideways span. “A few seconds” understates 6–24-second cases. `docs/LIMITS.md:82-89`, `app/services.py:175-199`

   5.6 REQUIREMENTS_TRACE claims results in about five seconds despite real-label p95 8.665 seconds and the new worst cases; its “ignoring only case and spacing” also omits typographic-quote normalization and hyphen repair. `docs/REQUIREMENTS_TRACE.md:9-12`, `docs/EVAL_REAL.md:33-34`, `app/pipeline/warning.py:131-160`, `app/pipeline/normalize.py:104-115`

   5.7 EVAL.md is internally current, but its 6.436-second degraded p95 and 6.548-second rotated median contradict the broad five-second story. `docs/EVAL.md:24-26`, `docs/EVAL.md:48`

   5.8 EVAL_REAL’s regeneration timestamp precedes its claimed fetch date. `docs/EVAL_REAL.md:3`, `docs/EVAL_REAL.md:62`

   5.9 D-035 overclaims “each image” and both directions; it also claims genuinely different names score under 70 without attached evidence. `docs/DECISIONS.md:43`, `app/services.py:169-189`

   5.10 D-037 internally contradicts itself: it calls `WOMAN` small-print noise, then acknowledges the label genuinely prints it. A clear printed word change is downgraded to review. `docs/DECISIONS.md:45`, `docs/EVAL_REAL.md:52`

   5.11 Older decisions still describe the removed `case` assessment and literal exactness. `docs/DECISIONS.md:30-31`, `docs/DECISIONS.md:37-40`

   5.12 `normalize.py` still says warning exactness is literal and does not use these helpers, although warning imports four of them. `app/pipeline/normalize.py:12`, `app/pipeline/warning.py:23-24`

   5.13 No surviving live threshold-90 claim found.

6. **Tests missing, highest damage first**

   6.1 `test_word_boundary_changes_are_not_exact`: reject `womens hould`, `acar`, and spaces inserted inside `GOVERNMENT`. `app/pipeline/warning.py:152-160`

   6.2 `test_bottler_fold_preserves_address_and_legal_identity`: `ACME LLC, Denver, CO` must not match `ACME, Denver` or `ACME Inc.`. `app/pipeline/normalize.py:126-136`

   6.3 `test_rescue_chooses_best_of_90_270_and_high_resolution`: 90° returns 0.6, 270° exact, high-resolution exact; exact must win. `app/services.py:175-198`

   6.4 `test_busy_rescue_does_not_change_the_verdict_silently`: identical batch inputs under contention must not alternate between rescued and absent. `app/services.py:166-201`

   6.5 `test_rotated_primary_read_can_still_rescue_the_other_orientation`: total-text winner lacks warning while discarded orientation contains it. `app/services.py:169-180`

   6.6 `test_interactive_rescue_queue_time_is_reported`: second acquisition wait must appear in timing. `app/services.py:167`, `app/services.py:208-213`

   6.7 `test_cancellation_mid_rescue_releases_after_inference`: assert slot remains held until fake inference completes, then returns to zero. `app/ocr/pool.py:148-164`

   6.8 `test_reading_order_with_heterogeneous_thickness_and_close_columns`: large display text must not merge two body columns. `app/pipeline/match.py:60-83`

   6.9 `test_bottler_evidence_retains_candidate_order_and_identity`: duplicated boxes/raw OCR order must not alter displayed found text. `app/pipeline/compare.py:99-107`

   6.10 `test_fetch_request_cap_is_absolute_and_resume_retries_partial_records`: include search, form, and images in the cap. `tools/cola_fetch.py:290-339`

   6.11 `test_real_summary_percentiles_and_false_positive_reads`: pin nearest-rank p95, origin context, and cross-image parsing. `tools/evaluate_real.py:140-156`, `tools/evaluate_real.py:247-250`

7. **Ship list**

   7.1 **Must — S:** Make exactness token-boundary-sensitive while retaining case-insensitive body comparison. `app/pipeline/warning.py:152-160`

   7.2 **Must — S:** Disable automatic rescue by default for submission, or at least for batch/extract, until it has a pass/time budget. This is the safest route back to the emphasized latency target. `app/config.py:42-56`, `app/services.py:136-146`

   7.3 **Must — M:** If rescue remains automatic, evaluate both orientations, permit high resolution after a partial result, handle already-rotated images, and make unavailable rescue explicit/deterministic. `app/services.py:166-201`

   7.4 **Must — M:** Restrict company folding to a leading production phrase and actual name suffix; preserve address tokens and avoid treating LLC/Inc. as interchangeable legal identities without review. `app/pipeline/normalize.py:118-136`

   7.5 **Must — M:** Re-run deployed single, missing-warning pair, large-image, and batch latency at this commit; replace pre-rescue claims. `README.md:38`, `docs/LOADTEST.md:65-75`

   7.6 **Must — S:** Correct stale exactness, batch, degraded-evaluation, hand-check, and D-035/D-037 documentation. `README.md:41-74`, `README.md:133-144`, `docs/DECISIONS.md:43-45`

   7.7 **Can wait — S:** Attribute rescue queue time and repair bottler evidence ordering. `app/services.py:167`, `app/pipeline/compare.py:99-107`

   7.8 **Can wait — M:** Harden heterogeneous/rotated reading order and duplicate-line handling. `app/pipeline/match.py:60-83`, `app/pipeline/warning.py:106`

   7.9 **Can wait — M:** Enforce fetch caps, output containment, session closure, and resumable partial images. `tools/cola_fetch.py:179-198`, `tools/cola_fetch.py:277-339`

   7.10 **Can wait — L:** Build a genuinely labeled real corpus and report precision/recall rather than approval-derived and “match-or-review” proxy metrics. `docs/EVAL_REAL.md:9-13`