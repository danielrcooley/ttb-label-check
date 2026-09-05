## 1. Bugs

*Static review only. References count lines from the first line after each file header. The planned README edits are treated as complete; excluded assets and deployment availability remain unverified.*

1. **High — single-screen results can describe different images from those displayed/exported.** `runCheck()` snapshots files only **after** awaiting verification, then repeatedly reads mutable `state.files`. Remove/replace images, select another sample, or press Start over during a slow request: old results can acquire new filenames/pixels, crash rendering, or reappear after clearing. Snapshot before submission and invalidate superseded requests. `app/static/app.js:178`, `app/static/app.js:194`, `app/static/app.js:197`, `app/static/app.js:243`

2. **High — replacing batch images can reuse old OCR.** `clearImages()` preserves `state.extractions`; extraction cache identity is only the filename/path. Remove images, select different contents under the same names, and rerun: old OCR is compared against the new application and displayed over new artwork. `app/static/batch.js:92`, `app/static/batch.js:183`

3. **High — decisions/results survive manual changes to a batch application.** Assigning an unmatched image changes `it.files` without clearing its decision or previous result. If the new extraction/comparison fails, export prefers the old verdict over the new error and includes the newly attached files. `app/static/batch.js:224`, `app/static/batch.js:473`, `app/static/render.js:300`

4. **High — duplicate application references share decisions and details.** `item.key` is the application reference, with no uniqueness check. Two spreadsheet rows with the same reference share `state.decisions`, `detailCache`, expansion state, and manual-assignment lookup. Approving one can approve both in the export. `app/static/batch.js:134`, `app/static/batch.js:373`, `app/static/batch.js:421`, `app/static/batch.js:471`

5. **High — malformed supplied alcohol values can allow Ready.** For malt/table wine, an unparseable nonempty value such as `six percent` follows the “application gives no alcohol content” branch and becomes Info. The supplied value was never compared. Distinguish absent from unparseable. `app/pipeline/compare.py:265`, `app/pipeline/compare.py:295`, `app/pipeline/compare.py:314`

6. **High — contradictory numbers can pass.** Net contents selects any matching value and ignores conflicting values elsewhere. Alcohol parses only one percent/proof per OCR line, so `40% ALC/VOL; 45% ALC/VOL` can Match an application stating 40%. Alcohol contradictions are also bypassed entirely when the application value is absent/unparseable. `app/pipeline/compare.py:270`, `app/pipeline/compare.py:295`, `app/pipeline/compare.py:326`, `app/pipeline/compare.py:400`, `app/pipeline/parsers.py:68`

7. **High — the earlier contrary-origin bug survives.** Expected `Italy` plus `Bottled in Napa, CA` becomes Mismatch: `country_named()` identifies the United States, and `_origin_check()` treats bottling location as contradictory product origin. The purported regression test instead uses `Bottled in Napa Valley`, avoiding the failing case. `app/pipeline/compare.py:51`, `app/pipeline/compare.py:126`, `app/pipeline/countries.py:85`, `tests/unit/test_countries.py:53`

8. **High — a two-line heading can falsely pass bold.** For `GOVERNMENT` / `WARNING: (1) …`, weight matching measures only the second fragment; regular GOVERNMENT plus bold WARNING can become a heading Match. Separately, the caps check includes the second line’s body text, so correctly capitalized heading words followed by mixed-case prose can incorrectly require review. `app/pipeline/warning.py:68`, `app/pipeline/warning.py:255`, `app/pipeline/warning.py:284`, `app/pipeline/typeface.py:78`

9. **High — notes can disappear during batch processing.** Notes are saved only on `change`, while completion updates replace the whole table. A note being typed can be removed before it commits. On either screen, committing a note rebuilds the controls during blur, potentially removing the Export/decision button before its click and losing keyboard focus. `app/static/render.js:290`, `app/static/batch.js:254`, `app/static/batch.js:431`, `app/static/app.js:265`

10. **High — overlapping batch runs are possible.** `start()` sets `running` only after awaiting health and has no reentry guard. Double-click Start or load the demo during an existing run: multiple pools share counters, abort controller, caches and item state. `app/static/batch.js:274`, `app/static/batch.js:287`, `app/static/batch.js:495`

11. **High — unexpected health JSON can hang batch indefinitely.** A successful `{}` health response makes `maxConcurrency` NaN. The pool launches nothing and never resolves. Successful compare JSON with `results: []` instead marks the item done without a comparison result, exporting it as `extract_only`. Validate successful response shapes. `app/static/api.js:18`, `app/static/batch.js:232`, `app/static/batch.js:263`, `app/static/batch.js:287`, `app/static/render.js:304`

12. **Medium — incomplete image lists can still produce Ready.** Missing CSV-listed images are displayed but do not prevent comparison or Ready; the missing list is absent from export. A complete-looking front can therefore pass while a listed back was never checked. `app/static/batch.js:142`, `app/static/batch.js:156`, `app/static/batch.js:228`, `app/static/batch.js:485`

13. **Medium — spreadsheet interpretation can change meaning silently.** A `Proof` column containing `90` becomes bare 90% ABV; separate ABV and Proof columns concatenate without units. Unknown imported values silently become false. A CSV field exceeding Python’s default field-size limit raises an uncaught `csv.Error`, producing 500 despite fitting the 2 MB upload cap. `app/csvio.py:46`, `app/csvio.py:183`, `app/csvio.py:193`, `app/csvio.py:202`

14. **Medium — numeric regexes can read suffixes or the wrong magnitude.** `17500 mL` can parse as `7500 mL`; `1045% ALC/VOL` as 45%; decimal-comma `0,750 L` is interpreted as 750 L. Numeric token boundaries and field-specific decimal handling are missing. `app/pipeline/parsers.py:16`, `app/pipeline/parsers.py:19`, `app/pipeline/parsers.py:47`, `app/pipeline/parsers.py:132`

15. **Medium — image pixels/coordinates have remaining edge cases.** Converting transparent artwork directly to RGB can turn black text on transparency into an unreadable black image. Coordinate mapping uses one nominal scale despite independently rounded dimensions; narrow strips can acquire materially wrong short-axis coordinates. `app/pipeline/images.py:100`, `app/pipeline/images.py:109`, `app/pipeline/images.py:149`

16. **Medium — aborted/failed batch work outlives its item.** `Promise.all()` rejects on the first failed image without settling sibling extractions. The batch can announce completion/reset while those promises continue updating shared caches. Backoff sleeps also ignore cancellation. `app/static/batch.js:188`, `app/static/batch.js:228`, `app/static/batch.js:266`, `app/static/batch.js:307`

17. **Medium — report numbers are misleading.** Batch ETA divides by concurrency twice: elapsed/completed already measures concurrent throughput. Paused/idle time accumulates into subsequent run totals. Single-screen “sending and receiving” also includes browser crop/render time and server work outside pipeline timing. `app/static/batch.js:291`, `app/static/batch.js:334`, `app/static/batch.js:337`, `app/static/app.js:197`, `app/static/app.js:226`

18. **Medium — address corroboration still accepts substrings and input order.** Expected `Orange, NJ` can be corroborated by `East Orange, NJ`; `_near()` uses the supplied OCR sequence rather than the reading order its documentation promises. `app/pipeline/compare.py:157`, `app/pipeline/compare.py:181`

## 2. The assignment, item by item

1. **About five seconds — partially met.** Clean single-user front/back requests meet the recorded target; two-user wall p95 is 6.408 s and concurrent-batch wall p95 is 6.366 s. Real-artwork service p95 is 7.330 s; sideways synthetic median is 6.386 s. D-018’s acceptance gate is not satisfied. `README.md:149`, `docs/EVAL.md:50`, `docs/EVAL_REAL.md:44`, `docs/DECISIONS.md:26`

2. **“My mother could figure out” / clean, obvious interface — supported by design, unproven by observation.** Numbered steps, samples and prominent actions exist. No novice-usability evidence remains under the requested edit; keyboard, note-loss and asynchronous-state defects weaken the claim. `app/static/index.html:49`, `app/static/app.js:178`, `docs/REQUIREMENTS_TRACE.md:10`

3. **Batch uploads of 200–300 applications — implemented, scale not demonstrated at the requested count.** The recorded browser run is **150 applications / 300 images**. The 300-request extract run is not 300 application comparisons. Pairing and state defects remain. `README.md:150`, `README.md:153`, `tests/browser/batch_scale.py:7`

4. **Exact warning wording — substantially implemented.** Canonical text, word/punctuation tokens, diffs and nonexact review/issue outcomes exist. Case, punctuation style and line-break normalization must be described consistently. D-032 remains fixed, with its disclosed accented-print limitation. `app/pipeline/warning.py:31`, `app/pipeline/warning.py:168`, `tests/unit/test_warning.py:253`

5. **GOVERNMENT WARNING in capitals and bold — partially met.** Both live format rows exist; uncertain bold is Needs review as D-047 requires. The split-heading bugs prevent full implementation of the two-word requirement. Removing the body-weight row correctly implements D-046. `app/static/render.js:141`, `app/pipeline/warning.py:301`, `app/pipeline/warning.py:68`

6. **Dave’s STONE’S THROW case / human judgment — met.** Case-only changes Match with a note; decisions are recorded by the user, separately from recommendations. `tests/unit/test_match.py:23`, `tests/integration/test_verify_api.py:112`, `app/static/render.js:281`

7. **Jenny’s angles, lighting and glare — partially met, appropriately limited.** Synthetic degradation measurements and rotation recovery exist; these do not establish performance on ordinary bottle photographs. A synthetic “Phone photo” is accurately described as tilted/blurred artwork. `docs/EVAL.md:25`, `tools/make_labels.py:1`, `app/static/samples/samples.json:25`

8. **Marcus’s firewall / no cloud verification APIs — met in the visible architecture.** OCR loads local models; frontend assets are same-origin; socket-blocking verification and a networking-disabled container smoke are provided. Binary contents themselves were excluded. `app/ocr/rapid.py:26`, `tests/integration/test_no_egress.py:19`, `.github/workflows/ci.yml:73`

9. **Standalone prototype, no COLA integration — met.** The application is a single stateless API/UI. Registry fetching is an evaluation tool outside verification. `app/main.py:60`, `tools/cola_fetch.py:1`

10. **“Don’t do anything crazy” / no sensitive storage — partially met.** No database or intentional content log exists, but oversized multipart uploads reach Azure ephemeral disk; CPU-heavy comparison can block the service. The unconditional no-storage claim exceeds the implementation. `docs/SECURITY.md:14`, `app/routes/api.py:155`

11. **Field list — present, with explicit limits.** Brand and class are required; alcohol/net contents are parsed; bottler/origin are compared when provided; imported-without-origin requires review; warning is separately assessed. Omitted bottler may still allow Ready under settled D-041/D-034 semantics. The numeric and origin bugs above affect correctness. `app/pipeline/compare.py:522`, `app/schemas.py:39`

12. **Sample distilled-spirit fields — met in source/tests.** OLD TOM, Bourbon, 45%/90 Proof and 750 mL are represented in sample JSON and a real-engine integration test. Excluded PNGs prevent independent pixel verification here. `app/static/samples/samples.json:6`, `tests/integration/test_verify_api.py:21`

13. **Additional labels and regulatory research hints — addressed.** Ten fictional products, degraded/problem variants and a 150-record registry evaluation are documented; regulatory sources and lists are recorded. Raw regulatory XML and artwork were excluded, so source/pixel fidelity is unverified here. `tools/make_labels.py:109`, `docs/EVAL_REAL.md:3`, `docs/REGULATIONS.md:3`

14. **Repository deliverable — substantially met, setup needs correction.** Source, tests, approach, tools and assumptions are provided. The default Docker recipe and unactivated-venv test instructions fail the “README alone” expectation. `README.md:87`, `docs/APPROACH.md:57`, `docs/APPROACH.md:69`

15. **Deployed working URL — documented, not independently verified.** A URL, deployment history, health endpoint and build identity exist. The supplied records do not prove current availability or deployment of commit 33ee00a. `README.md:10`, `app/routes/api.py:80`, `docs/LOADTEST.md:187`

16. **All six evaluation criteria — mixed.** Correctness loses points for §1; organization benefits from schemas/pure functions; local OCR is an appropriate scope choice; UX/error handling needs §5; requirements attention benefits from tracing but suffers from unsupported claims; evidence crops, measured OCR selection and browser batch orchestration demonstrate creative problem-solving. `README.md:193`, `app/pipeline/compare.py:1`, `docs/APPROACH.md:19`

17. **Trade-offs, limitations and independently filled gaps — met.** Assumptions and a detailed decision history are present. Statements that a second replica fixes latency, every error gives recovery guidance, and accessibility/usability requirements are demonstrated remain claims beyond the supplied evidence. `docs/APPROACH.md:69`, `docs/LIMITS.md:37`, `README.md:40`, `docs/REQUIREMENTS_TRACE.md:18`

## 3. Setup and run instructions, cold

1. **Default Docker recipe prevents browser access.** `--network none` isolates the container’s network namespace; publishing port 8000 does not make its loopback service reachable from the host browser. Use ordinary networking for the browser recipe; retain `--network none` for the existing in-container smoke proof. `README.md:93`, `AGENTS.md:51`, `.github/workflows/ci.yml:73`

2. **Tests use the wrong Python environment.** Runtime dependencies are installed with `.venv/bin/pip`, but the later test/tool commands use bare `pip`, `pytest`, `python`, `ruff` and `mypy` without activating that environment. Provide activation or consistently use its executables. `README.md:102`, `README.md:126`

3. **Windows instructions are incomplete.** Only the first pip command identifies its Windows equivalent; subsequent OCR install and uvicorn paths remain POSIX. The shell-specific browser/deployment examples also need identification. `README.md:103`, `README.md:104`, `README.md:105`, `tests/browser/README.md:11`

4. **Playwright setup is not in the main instructions.** The browser command requires an undeclared package and downloaded Chromium. Link the browser README or include both install commands. `README.md:129`, `requirements-dev.txt:1`, `tests/browser/README.md:11`

5. **State the supported baseline precisely.** CI and Docker exercise Python 3.12; “3.12 or newer” is broader than the evidence for pinned native wheels. Explain that models are already bundled, package installation needs network access, and startup takes a few seconds after dependencies/image construction. `README.md:99`, `README.md:108`, `.github/workflows/ci.yml:17`, `Dockerfile:3`

6. **Some required text assets are absent from this bundle.** Fixture `manifest.json` and model `MANIFEST.json` are consumed but not supplied as file sections. Their absence here prevents certifying a cold checkout; it does not establish that the repository lacks them. Samples themselves are correctly referenced under `app/static/samples/`. `tools/evaluate.py:70`, `app/ocr/rapid.py:26`, `README.md:115`

7. **Fixture regeneration is not environment-independent.** The README command overwrites committed fixtures using whichever system fonts resolve first; a fresh machine can produce different labels and evaluation results despite seed 42. Prefer evaluating the committed corpus, and document font-dependent regeneration. `README.md:133`, `tools/make_labels.py:37`, `tools/make_labels.py:83`

## 4. Documentation accuracy

1. **Usability evidence remains claimed elsewhere.** Removing the README clause leaves “an observed usability test is reported in the README” in the requirements trace. “Each one is met … checked by a test or measurement” also remains unsupported. `docs/REQUIREMENTS_TRACE.md:10`, `README.md:35`

2. **“Submitted build” measurement provenance is wrong.** The latest named load-test build is 77891db, while this review covers 33ee00a. The prominent batch row still cites 315 s, while the detailed newer row cites 495 s. Label historical measurements by actual build. `README.md:42`, `README.md:149`, `README.md:150`, `docs/LOADTEST.md:187`

3. **Local timing and real-warning percentages disagree.** The emphasized row’s local 2.7/3.1 s differs from EVAL’s 2.458/2.955 s. Real warning counts imply approximately **62% exact / 23% noise / 15% wording** among 148 located statements, not 62/22/16. `README.md:40`, `README.md:147`, `docs/EVAL.md:9`, `docs/EVAL_REAL.md:52`

4. **“Every batch image exactly once” is false literally.** Batch skips warning rescue but still runs the unconditional low-confidence/few-lines rotation retry. Say “one initial read, with orientation retry; no warning-rescue round.” `app/services.py:147`, `app/services.py:195`, `README.md:82`, `docs/APPROACH.md:27`

5. **Origin documentation describes a fix the code does not implement.** LIMITS says `Bottled in Napa, CA` is not evidence against an Italian wine; it remains a Mismatch. `docs/LIMITS.md:118`, `app/pipeline/compare.py:126`, `app/pipeline/countries.py:85`

6. **Physical size is not shown as “Not checked.”** APPROACH says it is; the live warning card has only capitals and bold. About also implies physical-size items are marked for confirmation. Describe physical size as outside the report. `docs/APPROACH.md:88`, `app/static/render.js:141`, `app/static/index.html:289`

7. **The warning table mislabels outcomes.** EVAL places every present-but-nonexact warning under Needs review, including wording issues. Its degraded table shows two reviews and zero mismatches despite an Issues verdict caused by warning wording. Store/report assessment, not just presence/exactness. `tools/evaluate.py:179`, `docs/EVAL.md:37`, `docs/EVAL.md:39`

8. **Exactness prose is inconsistent.** README omits typographic normalization and line-break hyphen repair; the trace includes them. Generic “a changed word is a mismatch” also needs the existing single-character exception, which treats `women`→`woman` as review. `README.md:43`, `docs/REQUIREMENTS_TRACE.md:12`, `app/pipeline/warning.py:198`

9. **Accessibility claims exceed tests and rendering.** The scripts do not establish keyboard-only operation or screen-reader usability; mobile testing bypasses CSP. Filters carry `aria-pressed` but no textual check mark, and several batch statuses lack icons despite “every status” wording. `app/static/index.html:315`, `app/static/batch.js:401`, `tests/browser/smoke_single.py:174`

10. **Security claims need narrower wording.** “Nothing sensitive is logged” ignores exception logging; “cross-origin isolation headers” is inaccurate without COEP; total process memory is not bounded solely by upload bytes × admission count. Images/results also leave the container in responses, contrary to the production-summary parenthesis. `docs/SECURITY.md:12`, `docs/SECURITY.md:20`, `docs/SECURITY.md:36`, `docs/SECURITY.md:67`

11. **Small stale claims remain.** The settings description says first XFF hop, implementation uses last; agency branding is configured but never rendered; the requirements trace links a nonexistent README “Deployment” section; AGENTS names the wrong no-egress test path. `app/config.py:30`, `app/security.py:87`, `README.md:242`, `docs/REQUIREMENTS_TRACE.md:22`, `AGENTS.md:15`

12. **Test count appears off by one.** Static expansion gives 208 unit cases, including two font-dependent cases, versus README’s 207; integration count 18 agrees. Historical decision/review descriptions of removed body-weight behavior should remain historical, with superseding decisions identified. Live schema/rendering contain no surviving body-weight row. `README.md:127`, `tests/unit/test_typeface.py:141`, `docs/DECISIONS.md:52`, `app/static/render.js:143`

## 5. User experience and error handling

1. **Recovery controls are unsafe during work.** Start over can be undone by a late single result; demo/replacement controls remain active during batch processing. This is especially visible on slow connections. `app/static/app.js:243`, `app/static/batch.js:495`

2. **Samples have unhandled failure paths.** Sample downloads do not check HTTP status and have no enclosing recovery handler. A failed fetch leaves “Loading…” busy indefinitely; clicking before sample metadata loads silently does nothing. `app/static/app.js:146`, `app/static/app.js:149`, `app/static/batch.js:495`

3. **400/413/415/422 — normal application envelopes display reasonably, framework errors do not.** The registered HTTP handler catches FastAPI’s subclass, while framework multipart errors can use Starlette’s base exception and return `{"detail": ...}`. `ApiError` then loses that detail. CSV intake additionally discards server hints. `app/security.py:226`, `app/static/api.js:10`, `app/static/batch.js:79`

4. **429/503 — extraction retries; comparison and CSV do not.** Batch extraction honors numeric Retry-After with bounded backoff, but transient compare failures become item errors requiring Resume. Single verification offers generic retry guidance without the server’s wait duration. These paths should be deliberate and consistent. `app/static/batch.js:200`, `app/static/batch.js:231`, `app/static/app.js:212`

5. **Network/unexpected JSON — misleading or stuck states.** Null error JSON crashes `ApiError`; malformed successful bodies are accepted and later mislabeled as network failures. A hanging single fetch has no cancel control, and startup status is never polled to completion. Request IDs needed by the 500 message are never displayed. `app/static/api.js:10`, `app/static/api.js:18`, `app/static/app.js:216`, `app/static/app.js:303`, `app/security.py:258`

6. **Batch silently rejects selected files.** Unsupported, empty and oversized files are simply skipped, without names, reasons or fixes. Unmapped spreadsheet columns are returned by the API but not shown. “Start” without CSV reads images rather than verifying applications, which deserves clearer action wording. `app/static/batch.js:39`, `app/static/batch.js:65`, `app/static/index.html:217`

7. **Keyboard navigation still has concrete failures.** Skip to main content changes Batch/About/Accessibility back to Check because its hash is treated as an unknown route. Details toggles rebuild and remove their focused button; streaming updates remove other focused table controls. `app/static/index.html:16`, `app/static/app.js:31`, `app/static/batch.js:418`

8. **Verdict wording overstates completeness.** “All checks match” can coexist with omitted bottler/origin; “Everything else matches” also covers unchecked fields. “Warning: missing” states more than “not read.” “On-device” in About obscures that images go to the server. `app/pipeline/compare.py:507`, `app/pipeline/compare.py:518`, `app/static/render.js:265`, `app/static/index.html:283`

9. **Evidence can disappear without explanation.** Browser-unsupported images, notably TIFF, have no rendered-preview fallback; bitmap failures silently omit crops, and figure images have no error handling. Multi-image checks show only one image’s crop. The user may receive a verdict without usable visual evidence. `app/static/render.js:161`, `app/static/render.js:218`, `app/static/render.js:230`, `app/static/render.js:242`

10. **Phone/zoom/assistive coverage is narrower than claimed.** Single-screen viewport reflow is tested; batch phone/zoom behavior and actual screen-reader navigation are not. Forced-color decisions have explicit state styling, but reduced-motion users still receive unconditional smooth result scrolling. `tests/browser/smoke_single.py:174`, `app/static/app.css:170`, `app/static/app.js:209`

## 6. Security and privacy

1. **High — public `/compare` can block all requests.** Up to 100 items × 2,000 lines undergo synchronous span generation, sorting and fuzzy comparison on the event loop. Admission limits concurrent requests, not one request’s CPU cost; health is therefore not guaranteed responsive under this load. `app/routes/api.py:153`, `app/routes/api.py:155`, `app/pipeline/match.py:123`

2. **High — unconditional no-storage promise is false on Azure.** Oversized multipart parts spool before route validation; the deployment config supplies no memory-backed temporary volume. SECURITY discloses ephemeral disk, but the banner/README say no upload is stored. Enforce memory-only rejection or narrow the public promise explicitly. `app/main.py:39`, `app/routes/api.py:55`, `docs/SECURITY.md:14`, `app/static/index.html:21`

3. **Medium — exception and access logging exceed the stated policy.** Generic exception logging includes exception messages and traceback; internal validation errors can contain OCR values. Default uvicorn access logging also remains enabled. Custom logs interpolate arbitrary API paths into an unescaped JSON-looking format. `app/security.py:198`, `app/security.py:253`, `app/main.py:24`, `Dockerfile:45`

4. **Medium — limits require deployment qualifications.** There is no application body-read deadline, and keep-alive is not one. Omitting `X-Batch` obtains interactive priority. Per-client identity depends on actual ingress XFF behavior and uvicorn proxy processing; the supplied tests only construct request scopes. Global caps remain useful. `app/security.py:83`, `app/routes/api.py:121`, `docs/SECURITY.md:21`, `tests/unit/test_security.py:59`

5. **CSV export guard is sound for its stated prefixes.** Cells are quoted, embedded quotes doubled, and leading whitespace/control characters before `= + - @` are guarded. OCR/user text uses text nodes; localStorage holds only the theme. No additional live XSS path found. `app/static/render.js:310`, `app/static/render.js:22`, `app/static/theme.js:5`

6. **Container/header basics are appropriate.** Non-root execution, same-origin CSP, frame restriction, no-store API responses and explicit application proxy trust are present. Dependency auditing is advisory and transitive installs are not locked, as disclosed; this is not a release-quality supply-chain proof. `Dockerfile:36`, `app/security.py:24`, `docs/SECURITY.md:45`

7. **No credential or private key found in the supplied text.** Author identity, GitHub account, public domain/Azure hostname, stakeholder names and public COLA identifiers/business addresses are visible. Real artwork and binary assets were excluded, so this is not a complete repository secret/data scan. `LICENSE:3`, `README.md:10`, `docs/EVAL_REAL.md:62`, `tests/unit/test_normalize.py:46`

## 7. Code quality and organisation

1. **Browser state ownership is the main organization weakness.** Mutable global state, overlapping async operations and repeated DOM reconstruction cause most serious bugs. Add explicit run identities, immutable submitted inputs and cache invalidation before broader refactoring. `app/static/app.js:10`, `app/static/batch.js:15`

2. **Load tools can report success while the service fails.** `steady()` calculates throughput from attempted requests, not successful ones; `main()` exits successfully regardless of response failures. The measurement shell lacks `set -e`. Burst health starts before the burst and repeatedly records zero OCR inflight, so it does not prove responsiveness under saturation. `tools/loadtest.py:106`, `tools/loadtest.py:127`, `tools/loadtest.py:154`, `tools/measure_deployed.sh:9`

3. **Typeface fallback does not match its description.** `best_drop` starts at zero and every positive ratio can select a gap, including same-weight ratios. Therefore “when nothing drops, choose nearest typographic estimate” is generally unreachable when usable candidates exist; it selects the largest fluctuation. No corpus evidence here quantifies the resulting false-Match risk. `app/pipeline/typeface.py:213`

4. **One OCR tool ignores an advertised option.** Process mode calls `load(Path(path))` with default 1600, ignoring `--max-side`, while printing the requested value in its report. Its direct RapidOCR path also differs from the product’s alphabet/preprocessing configuration. `tools/ocr_eval2.py:96`, `tools/ocr_eval2.py:51`

5. **Evaluation reproducibility needs stronger provenance.** Real evaluation defaults do not identify the actual sampling window or record set; raw results remain local. Hand-check text is carried forward automatically. The real evaluator also uses default bold thresholds rather than the Settings thresholds used by verification. `tools/evaluate_real.py:140`, `tools/evaluate_real.py:306`, `tools/evaluate_real.py:354`, `docs/EVAL_REAL.md:3`

6. **Fetcher limitations remain as previously deferred.** Request cap is checked between records, not before every request; partial image failures become completed records and are not retried on resume. `batch_tally.py` also writes temporary spreadsheet/export data and exits successfully even with item errors. These are evaluation-tool behaviors, not verification-path storage. `tools/cola_fetch.py:304`, `tools/cola_fetch.py:325`, `tools/batch_tally.py:78`, `tools/batch_tally.py:134`

7. **Small cleanup only.** `jinja2` has no visible use; agency-name configuration is unwired; `.row-btn` styles have no corresponding element; error parsing and verdict maps are duplicated across frontend modules. Historical review documents are useful provenance but should not read as current implementation specifications. `requirements.txt:10`, `app/config.py:28`, `app/static/app.css:87`, `app/static/api.js:18`, `app/static/batch.js:60`

## 8. Tests

1. **Add browser tests for immutable verification inputs and stale-response rejection.** Delay a request, replace/remove files, start another sample, then reset; assert verdict, images and exported filenames remain associated with the submitted request. `app/static/app.js:191`

2. **Add batch cache/decision identity regressions.** Replace same-name images, duplicate application references, attach another image after approval, and force the recomparison to fail. Assert no old OCR, verdict or decision survives incorrectly. `app/static/batch.js:183`, `app/static/batch.js:473`

3. **Add note durability and actual keyboard tests.** Type while batch rows finish; click Export directly from the note field; toggle Details and use Skip to main content. Assert saved text, download and focus. `app/static/render.js:290`, `app/static/batch.js:431`

4. **Add the complete client error matrix.** Cover 400/411/413/415/422/429/503/500, Starlette `detail`, HTML, null, empty/malformed success bodies, network rejection, stalled fetch, failed sample downloads and malformed health capacity. `app/static/api.js:18`, `app/static/batch.js:287`

5. **Add numeric/CSV semantic cases.** Supplied-but-unparseable optional ABV; contradictory numbers on one line and across images; Proof-only columns; duplicate aliases; unknown imported flags; long CSV fields; oversized numeric tokens and decimal commas. `tests/unit/test_csvio.py:1`, `tests/unit/test_parsers.py:1`

6. **Correct the origin regression and add split-heading checks.** Test the actual `Italy`/`Bottled in Napa, CA` example; separately vary GOVERNMENT and WARNING weight/case with mixed-case body continuation. Existing tests miss both defects. `tests/unit/test_countries.py:53`, `tests/unit/test_warning.py:71`

7. **Add service stress/failure tests.** Exercise maximum compare work while checking health; request cancellation and exceptions through middleware; sibling extraction failures; pause/reset during backoff; overlapping starts. Current limiter tests do not test middleware release on every exit path. `tests/unit/test_security.py:1`, `tests/unit/test_pool.py:1`

8. **Several tests can pass with advertised behavior broken.** Batch smoke prints rather than asserts verdict counts, crop counts and exported values. Single smoke does not assert photo outcome or crop/overlay presence; its focus check allows `None` and runs after export. The “every image exactly once” test uses an engine that never triggers low-confidence retry. `tests/browser/smoke_batch.py:59`, `tests/browser/smoke_single.py:23`, `tests/browser/smoke_single.py:108`, `tests/unit/test_services.py:134`

9. **Missing acceptance evidence:** 300 complete applications through the browser; batch phone/zoom/keyboard checks; measured memory; deployed five-second gate at the tagged build. The real-face tests may skip, and the CI latency assertion permits 15 seconds. `tests/browser/batch_scale.py:91`, `tests/unit/test_typeface.py:141`, `tests/integration/test_verify_api.py:35`

## 9. Ship list

**Must change before the tag**

1. Fix single/batch input snapshots, cache invalidation, run reentry and stale-response handling; make decisions belong to a specific completed comparison. `app/static/app.js:178`, `app/static/batch.js:183`
2. Fix duplicate batch keys and note loss; block or explicitly qualify incomplete image sets. `app/static/batch.js:134`, `app/static/render.js:290`
3. Fix malformed alcohol handling, contradictory numeric statements, Proof CSV semantics, contrary-origin inference and split-heading format checks. `app/pipeline/compare.py:263`, `app/csvio.py:46`, `app/pipeline/warning.py:68`
4. Normalize error bodies, validate successful JSON, recover failed sample loads and expose request IDs; prevent malformed health data from hanging batch. `app/static/api.js:18`, `app/static/batch.js:287`
5. Correct the Docker/venv instructions and remove unsupported current-build, usability, batch-read and timing claims. `README.md:93`, `README.md:126`, `docs/REQUIREMENTS_TRACE.md:10`
6. Bound comparison CPU work and resolve the unconditional no-storage promise. `app/routes/api.py:155`, `docs/SECURITY.md:14`
7. Run focused regressions, then record final-build deployment checks and a 300-application browser run. Report the five-second gate as unmet wherever it remains unmet. `tests/browser/batch_scale.py:91`, `docs/DECISIONS.md:26`

**Leave alone before submission**

1. Keep D-032, D-041, D-046 and D-047 policies; repair their implementation without changing the agreed verdict matrix. `docs/DECISIONS.md:40`, `docs/DECISIONS.md:49`, `docs/DECISIONS.md:54`
2. Keep local OCR, vendored assets, the current engine interface and bounded rescue design. Do not add cloud models, another engine or broad photo enhancement. `app/ocr/rapid.py:1`, `app/services.py:198`
3. Keep the relative bold estimator/thresholds pending a labelled corpus; fix split-heading coverage and misleading fallback logic without opportunistic retuning. `docs/LIMITS.md:39`, `app/pipeline/typeface.py:213`
4. Keep authentication, persistent audit storage, COLA integration and broad framework refactoring outside this prototype. `docs/SECURITY.md:50`
5. Preserve historical measurements/reviews as dated evidence; correct their presentation instead of erasing the development record. `docs/LOADTEST.md:1`, `docs/DECISIONS.md:3`

The strongest feature is the traceable local verification pipeline: measurements, explicit limits and evidence pixels make its recommendations inspectable. The weakest is browser state integrity: ordinary edits, retries and batch activity can associate a result or decision with the wrong inputs, undermining an otherwise carefully explained system.