## 1. Missed requirements

1. “**If we can't get results back in about 5 seconds, nobody's going to use it.**” Sections 3 and 14 measure throughput, but §3 permits a 6-second soft deadline and §12 does not require deployed, end-to-end p95 under five seconds. Test the common two-image application through the UI/API, including upload and preprocessing.
2. “**my mother could figure out**” is addressed with accessibility features, not demonstrated simplicity. Sections 7, 10, and 12 add two screens, pairing confidence, filters, shortcuts, evidence controls, and many statuses. Require an observed, unprompted usability test with older/nontechnical users and record completion time and errors.
3. “**handle batch uploads**” is addressed strongly in §§2–3, 7, and 12. Preserve streaming progress, per-file failures, cancel, and export; the speculative fuzzy pairing is not required by the brief.
4. The warning must be “**exact**.” Section 5’s “OCR-tolerant similarity” is too permissive unless every textual or punctuation deviation remains a mismatch or review—not a pass. Use a warning-specific comparator preserving the colon, `(1)`, `(2)`, commas, and periods.
5. The “**Government Health Warning Statement**” is covered, including multiple label images. However, §12 must explicitly require golden tests for exact text, title-case heading, missing punctuation, missing paragraph `(2)`, missing anchor bold, and an all-bold warning.
6. The brief lists “Name and address of bottler/producer” and “Country of origin for imports.” Sections 5, 11, and 12 reduce these to optional CSV fields or declare phrasing rules out of scope. At minimum, compare supplied application values and report missing/not-found; make origin conditional on imported products.
7. “README with setup and run instructions” is buried inside a nine-document documentation program in §12. DoD should explicitly require that a clean reviewer can run the app from the README alone.
8. “A working core application with clean code is preferred over ambitious but incomplete features.” Sections 10–13 violate that instruction through two deployments, nine documents, standards-of-fill logic, PDF support, authentication, an SBOM, keyboard triage, duplicate detection, print reports, and extensive procurement signaling.

## 2. Wrong calls

1. Reverse §12’s two-host deployment. Ship one reliable host, preferably Azure Container Apps, with a tested local Docker fallback; retain Fly only as an emergency deployment option.
2. Reverse §§0 and 10’s automatic fuzzy many-to-one pairing as the default. Back labels often lack brand, ABV, and net contents, so they can confidently attach to the wrong application. Default to the explicit `images` column; make fuzzy suggestions reviewable and manually reassignable.
3. Replace §3’s “up to 1000 compare calls” with one chunked batch endpoint. Section 11 later mentions bulk chunks of 100, but §1 and the repository layout define no bulk contract.
4. Replace §3’s two independent semaphores. “Interactive gets full CPU” plus “batch gets CPU minus one” can exceed total CPU. Use one shared capacity limiter with interactive priority/reservation.
5. Reverse §4’s assumption that a soft deadline controls an OCR thread. Timeout cannot stop an ONNX call already running; timed-out work can retain capacity and trigger a collapse. Limit passes cooperatively and use a killable process only if hard cancellation proves necessary.
6. Reverse §5’s relative size check against brand text. Brand height has no regulatory relationship to warning type size. For photos, report “physical size not verifiable”; for PDFs or artwork with trustworthy dimensions, calculate actual size.
7. Cut §11’s PDF/GIF expansion unless representative inputs prove it necessary. PDFium adds native code, page semantics, image-size amplification, and coordinate/security work to a six-day prototype.
8. Reverse §6’s claim that “No persistence” is proved by a read-only filesystem. `/tmp` is writable, and Starlette multipart uploads may spool there. Either implement bounded streaming or accurately disclose ephemeral temporary-file use.
9. Agree with §§1 and 10–12 on local deterministic OCR, baked models, no core LLM, traceable findings, and a human decision.

## 3. Over-scope

1. Cut first: §13 GitHub-profile cleanup, submission-note drafting, talking-points material, branding slot, keyboard shortcuts, paste/camera input, duplicate detection, server-rendered report, and print view. None appears in §12’s DoD.
2. Cut advanced photo recovery from §§10–11: glare handling, four-way rotation, zoom re-OCR, and AI-generated photo labels. Keep one degraded-photo test because Jenny explicitly calls photos “maybe out of scope.”
3. Reduce §12 DoD #6 from two hosts plus monitoring to one deployed host, one tested Docker command, SHA/version display, and a final availability check.
4. Cut standards-of-fill validation and beverage-type inference from §12’s core. They exceed the brief’s comparison task and create regulatory false-positive risk.
5. Reduce §12 DoD #2 to explicit filename/CSV pairing, streaming results, triage, and export. Add fuzzy pairing only after the 300-item explicit path is reliable.
6. Cut the access gate, SBOM, hash-pinned lockfile, Swagger UI vendoring, and exhaustive procurement hardening before cutting core tests, error handling, or accessibility basics.
7. Reduce §12 DoD #5 to README, APPROACH/DECISIONS, REQUIREMENTS_TRACE, and LIMITS/SECURITY. Fold PROCESS, agent instructions, and notices into those files where practical.
8. If still late, cut evidence crops from §12 DoD #1 but retain click-to-highlight. Do not cut exact-warning tests, the batch path, end-to-end p95 measurement, the eval, no-egress proof, or the single deployment.

## 4. Technical risks the plan underestimates

1. Decorative OCR: confidence is not field accuracy, and expected-value fuzzy search can conceal bad OCR. The Day-0 bake-off needs curved, condensed, outlined, gold-on-black, low-contrast, and mixed-case brands; report exact field recall, false matches, and latency—not mean OCR confidence.
2. Python wheels: ARCHITECTURE inherits Python 3.12 from PLAN; keep it. Enforce `requires-python ==3.12.*`, build Linux/amd64 in CI, and lock RapidOCR, ONNX Runtime, OpenCV, Pillow, and PDFium from that environment. Do not let a Windows Python 3.13 workstation define the lock.
3. ORT concurrency: `intra_op_num_threads=1` and `OMP_NUM_THREADS=1` may not disable all inter-op/provider pools. Verify actual process thread count and throughput at concurrency 1/2/3; a semaphore limits requests, not internal ORT threads.
4. Engine memory: one complete RapidOCR engine per worker may duplicate three model sessions. Measure resident memory after warm-up and under two simultaneous images before asserting that 1 GB works.
5. Coordinate mapping: preserve quadrilaterals, not only axis-aligned boxes; compose EXIF mirroring, rotation, crop, resize, deskew, and PDF-page transforms. Return normalized coordinates in one canonical oriented-image space and test all eight EXIF orientations plus CSS `object-fit`.
6. Client-side evidence crops may disagree with server orientation because browsers decode EXIF differently. Generate the displayed preview through the same canonical orientation or return a canonical preview asset.
7. USWDS without a build step is viable only by vendoring compiled `dist` CSS, JS, fonts, and images with their relative paths intact. Test sprite references, font URLs, CSP behavior, component JavaScript, and asset licensing; do not copy SCSS expecting it to work directly.
8. Azure Container Apps: explicitly configure external ingress, `targetPort`, CPU/memory pair, `minReplicas: 1`, startup/readiness/liveness probes, model-startup allowance, registry access, secrets, and revision traffic. Verify the configured cost instead of repeating the “~$10” estimate.
9. The §3 six-second deadline is per image, while Sarah’s expectation is results per application. A normal front/back application may run two OCR jobs serially or contend with batch work. Publish application-level p50/p95 under concurrent load.
10. Multipart limits are easy to apply after buffering. Enforce aggregate and per-file caps while streaming; multi-image `/verify` must not admit N × 10 MB unchecked.
11. Browser batch “resume is trivial” is overstated. It works only while the tab and file objects survive. A refresh loses extraction, pairing, notes, and decisions; state this plainly and test unload/export behavior.
12. Pairing is both ambiguous and potentially \(N \times M\). A warning-only back image may have no useful match signal. Require explicit/manual pairing before treating a grouped application as ready.
13. PDF rendering multiplies input size and exposes native parsing code. If retained, cap pages, rendered pixels, time, and total output independently of the uploaded-byte limit.

## 5. Reviewer's-eye check

1. Correctness/completeness: points lost for omitting producer/address and import origin, accepting an inexact warning, or falsely flagging valid wine/beer. Points earned by beverage-specific golden fixtures, expected-versus-found evidence, and a zero-false-pass warning suite.
2. Code quality/organization: points lost if the many endpoints, middleware, duplicated client/server normalization, and nine documents produce more framework than working logic. Points earned by a small dependency-injected pipeline, typed schemas, focused tests, and one readable request path.
3. Appropriate technical choices: local OCR, one container, baked models, and no egress earn points. Two hosts, PDF support, automatic fuzzy pairing, and unmeasured thread assumptions look like poor scope control.
4. UX/error handling: the three one-click samples, plain statuses, progressive batch table, and highlights earn points. Opaque auto-pairing, no obvious manual reassignment, excessive controls, or a result after five seconds lose them. Add an observed novice usability result, not a “mother test” checklist.
5. Attention to requirements: a trace from all five bold phrases to executable acceptance tests earns heavily. The current §12 DoD weakens that by omitting a hard deployed p95 gate and conditional producer/origin checks.
6. Creative problem-solving: evals, no-egress proof, evidence-to-pixels, and false-alarm measurement are strong differentiators. Publish an error analysis with representative failures and threshold rationale; otherwise the architecture reads as promises rather than engineering evidence.

## 6. Domain check

1. Encode the complete prescribed §16.21 text, including `GOVERNMENT WARNING:`, both numbered clauses, capitalization of “Surgeon General,” and both commas. TTB examples treat missing commas as corrections; do not run the generic punctuation-stripping normalizer over this check. Verify against [27 CFR §16.21](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-16/section-16.21).
2. Section 10 misattributes “separate and apart” to §16.22; it is in §16.21. Section 16.22 covers legibility, contrast, capitalization/bold, compression, characters per inch, type size, and label attachment.
3. Section 10 is correct that only “GOVERNMENT WARNING” must be bold and the remainder may not be bold. The legal thresholds are 1 mm at ≤237 mL, 2 mm at >237 mL through 3 L, and 3 mm above 3 L, with corresponding 40/25/12 characters-per-inch maxima. Verify [27 CFR §16.22](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-16/section-16.22).
4. Part 16 applies to beverages containing at least 0.5% ABV and intended for human consumption. “Mandatory on all alcohol beverages” is acceptable brief shorthand but should not become an unconditional domain rule.
5. Section 5’s wine rule needs precision: under Part 4, numerical ABV may be omitted for wine at 14% or less only when “table wine” or “light wine” supplies the designation; the practical COLA scope begins at 7%. Verify [27 CFR §4.36](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-4/subpart-D/section-4.36).
6. “Malt beverages ABV optional federally” is incomplete. Under §§7.63 and 7.65 it becomes mandatory when alcohol derives from added nonbeverage flavors/ingredients, and state law can also require it. Verify [27 CFR §§7.63–7.65](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-7/subpart-E).
7. Distilled spirits mandatory information includes name/address as well as brand, class/type, ABV, and net contents; some items have same-field-of-vision requirements. Section 12’s five-check DoD misses this. Verify [27 CFR §5.63](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-5/subpart-E/section-5.63).
8. Standards-of-fill lists changed in January 2025. If retained, copy the current authorized lists and exceptions from [§5.203](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-5/subpart-K/section-5.203) and [§4.72](https://www.ecfr.gov/current/title-27/chapter-I/subchapter-A/part-4/subpart-H/section-4.72), date the source, and test newly added sizes. Do not infer actual container capacity conclusively from OCR text.
9. Malt beverages have no analogous federal fixed-size list, but net-content expression rules still apply. “No standards of fill” must not become “no net-contents rules.”
10. Country-of-origin wording is not safely reducible to Parts 4, 5, and 7; customs marking rules may control. Keep it as application-versus-label comparison unless the relevant Title 19 provisions are also verified.

## 7. Top five

1. Replace §12 with a lean DoD: one host, concise docs, explicit batch pairing, and no PDF/standards-of-fill/procurement extras until the core is green.
2. Make the exact-warning path truly exact and verify §§16.21–16.22, including punctuation, both clauses, anchor bold/caps, non-bold body, applicability, and measurable format limits.
3. Add a hard acceptance gate for deployed end-to-end p95 under five seconds on a normal front/back application, including concurrent batch load.
4. Include producer/name-address and conditional import-origin comparison, and correct the wine and malt-beverage requiredness rules.
5. Fix the execution design before coding: one priority-aware OCR limiter, honest timeout semantics, bounded multipart handling, and a canonical tested coordinate system.