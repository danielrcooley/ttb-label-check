1. **Bugs introduced**

1.1 **Critical:** ASCII masking can turn genuinely accented warning text into the required ASCII spelling, yielding `ready_for_approval` for wording that is not physically exact. The evidence crop does not cure the false verdict. `app/ocr/alphabet.py:23-50`, `app/pipeline/compare.py:252-255`

1.2 **High:** Any `not_checked` check now permits Ready, not merely omitted bottler/origin. An uninterpretable required net-contents value becomes `not_checked`, so a verification can say Ready without comparing net contents. `app/pipeline/compare.py:173-176`, `app/pipeline/compare.py:252-255`

1.3 **High:** Alcohol candidates are compared only by rounded percentage. Two 45% statements with conflicting proofs can pass depending on line order; a matching candidate can hide the other proof. `app/pipeline/compare.py:100-104`, `app/pipeline/compare.py:135-156`

1.4 **High:** Split percent/proof statements are not joined when either half parses. A label/application both stating wrapped `45%` and `80 Proof` becomes conflicting 45%/40% label content rather than the intended consistency assessment. `app/pipeline/compare.py:93-106`, `app/pipeline/parsers.py:69-76`

1.5 **High:** `0%` cannot parse because alcohol values must be greater than zero; therefore a `0.0%` malt beverage does not take the under-0.5% warning exemption and can be reported as missing a mandatory warning. `app/pipeline/parsers.py:65-68`, `app/pipeline/parsers.py:77-82`, `app/pipeline/compare.py:305-316`

1.6 **High:** JPEG `draft()` changes `im.size`; the returned `width`, `height`, and `scale` therefore describe the reduced decode, not the oriented original promised by the API. Large-JPEG crops are then skipped by the dimension guard. `app/pipeline/images.py:83-108`, `app/schemas.py:3-5`, `app/static/render.js:218-235`

1.7 **High:** Rebuilding batch items does not clear decisions. After changing images or CSV content, an approval keyed by the same application ID can be exported against new inputs. Failed replacement CSVs also do not increment `inputVersion`. `app/static/batch.js:55-75`, `app/static/batch.js:118-120`, `app/static/batch.js:318-325`, `app/static/batch.js:430-436`

1.8 **Medium:** `not_required` is not rendered. An absent warning is shown as “Not found”/“missing,” while the backend verdict is Ready; a present exact warning is displayed as Needs review. The backend Ready summary also falsely says the warning is exact. `app/static/render.js:122-143`, `app/static/batch.js:310-315`, `app/pipeline/compare.py:238-255`

1.9 **Medium:** Alcohol evidence now contains every candidate, possibly across images, but crop bounds combine all evidence while decoding only the first evidence image. This produces a wrong or oversized crop. `app/pipeline/compare.py:101-104`, `app/static/render.js:212-235`

1.10 **Medium:** Folder-relative identity is not usable in the CSV: matching strips both a listed relative path and stored keys to basenames, so `folder-a/back.png` cannot disambiguate duplicate basenames. Display and export also discard the path. `app/static/batch.js:28-30`, `app/static/batch.js:92-99`, `app/static/batch.js:344-345`, `app/static/batch.js:433-436`

1.11 **Low:** Early 400/411/413/429/503 middleware responses omit `Server-Timing`; it is added only after `call_next`. `app/security.py:132-170`, `app/security.py:178-180`

1.12 No current pool leak found. Current callers invoke each yielded runner sequentially, making the cancellation callback sound. The abstraction would release early if multiple runner futures were launched concurrently and the last-added one finished first. `app/ocr/pool.py:146-164`, `app/services.py:100-104`, `app/services.py:132-133`

2. **Fidelity to review-002 dispositions**

2.1 **1.9 narrower:** Under-0.5% is implemented, but exactly 0% is unparseable. `docs/reviews/002-code-review.dispositions.md:24`, `app/pipeline/parsers.py:65-68`, `app/pipeline/compare.py:305-306`

2.2 **1.12 narrower:** Items rebuild after successful input changes, but old decisions survive and a failed replacement CSV is not versioned. `docs/reviews/002-code-review.dispositions.md:27`, `app/static/batch.js:55-75`, `app/static/batch.js:118-120`

2.3 **1.14 narrower:** The disposition permits a pure dimension swap; the implementation skips every mismatch. Large JPEG draft decoding also creates mismatches itself. `docs/reviews/002-code-review.dispositions.md:29`, `app/static/render.js:222-225`, `app/pipeline/images.py:92-108`

2.4 **2.2 incomplete:** The documented Azure deployment does not mount `/tmp` in memory, while SECURITY says the deployment does. `docs/reviews/002-code-review.dispositions.md:35`, `docs/DEPLOY.md:46-53`, `docs/SECURITY.md:14-19`

2.5 **3.7 incomplete:** Uvicorn keep-alive timeout is configured, but that is not a slow-body timeout; the supplied deployment/security docs do not state that slow-client protection is delegated to ingress. `docs/reviews/002-code-review.dispositions.md:51`, `Dockerfile:38`, `docs/SECURITY.md:24-43`

2.6 **5.1 not completed:** The README still has deployed placeholders, and the attached deployed run records p95 28,067 ms rather than under five seconds. `docs/reviews/002-code-review.dispositions.md:70`, `README.md:38`, `README.md:136-137`, `docs/LOADTEST.md:47-50`

2.7 **5.2 not completed:** Usability evidence remains `_USABILITY_RESULT_`. `docs/reviews/002-code-review.dispositions.md:71`, `README.md:39`

2.8 **5.6 broader:** Ready was authorized for absent bottler/origin data; allowing every present or future `not_checked` check makes the change broader than stated. `docs/reviews/002-code-review.dispositions.md:75`, `app/pipeline/compare.py:252-255`

2.9 **Docs disposition incomplete:** `Server-Timing` is not on early middleware responses. `docs/reviews/002-code-review.dispositions.md:79-84`, `app/security.py:132-180`

3. **Alphabet restriction — D-032**

3.1 **Blank:** Index zero is assumed to be blank without validating the decoder vocabulary. Any separately named `"blank"` is also retained, potentially preserving two classes. `app/ocr/alphabet.py:23-29`

3.2 **Shape:** Only `[batch,time,class]` arrays with an exact class count are masked. A library change to two dimensions, transposed axes, or a changed vocabulary silently restores unrestricted decoding while health still reports printable ASCII. `app/ocr/alphabet.py:46-51`, `app/ocr/rapid.py:48-53`

3.3 **Probabilities/logits:** `p.min() < 0` is only a sign heuristic, not a representation check. Nonnegative logits are treated as probabilities; suppressed classes become zero rather than impossible. `app/ocr/alphabet.py:35-36`, `app/ocr/alphabet.py:46-50`

3.4 **Confidence:** Probability outputs are masked but not renormalized. The selected ASCII runner-up retains its potentially tiny original probability, so quality, rotation retry, readability, and read selection now consume confidence from a different distribution. `app/ocr/alphabet.py:49-51`, `app/services.py:61-83`, `app/services.py:98-104`

3.5 **Library internals:** D-032 relies on undocumented-looking `text_rec`, `postprocess_op`, and `character` attributes. The version pin reduces immediate risk, but initialization should validate them and fail closed. `app/ocr/rapid.py:47-53`, `requirements-ocr.txt:3`

3.6 **Batch ordering:** The current three-dimensional wrapper preserves batch ordering; that part is sound. `app/ocr/alphabet.py:46-51`

3.7 **Docs are not honest enough:** Masking does not map an accent to its base letter; it selects the highest-scoring allowed class, which may be the base, blank, or another character. More importantly, an accented character inside the statutory warning can become ASCII and falsely pass as exact. `docs/LIMITS.md:63-68`, `docs/DECISIONS.md:40`, `README.md:143`, `app/ocr/alphabet.py:46-51`

3.8 **Evaluation provenance missing:** The evaluator records engine/alphabet metadata but no longer emits it into EVAL.md, so the published evaluation cannot establish that D-032 was enabled. `tools/evaluate.py:106-107`, `tools/evaluate.py:178-197`, `docs/EVAL.md:1-62`

4. **CI, Dockerfile, requirements, deployment**

4.1 **High:** The container job can publish while the independent lint/type/unit/integration job is failing; it has no `needs: test`. `.github/workflows/ci.yml:13-46`, `.github/workflows/ci.yml:47-90`

4.2 **High outside Azure:** The image forces `TTB_TRUST_PROXY=true`. The recommended direct `docker run -p` exposes the app without a trusted ingress, allowing spoofed rightmost XFF values to evade per-client admission. Configure trust in deployment, not the image. `Dockerfile:27-29`, `README.md:80-82`, `app/security.py:83-88`

4.3 **Medium:** `--no-deps` makes the manually copied RapidOCR dependency list an upgrade hazard. Direct requirements are pinned, but transitive dependencies from FastAPI, `uvicorn[standard]`, requests, and others are not locked or hash-pinned. `requirements.txt:1-24`, `requirements-ocr.txt:1-3`

4.4 **Medium:** Dependency audit is advisory and cannot fail CI despite `--strict`. `.github/workflows/ci.yml:44-45`

4.5 **Medium:** CI stores broad ACR admin credentials as repository secrets. The runbook acknowledges the better `AcrPush` service-principal option, but later incorrectly says no registry password is stored anywhere. `docs/DEPLOY.md:27-35`, `docs/DEPLOY.md:56-57`

4.6 **Low:** Concurrent master workflows can finish out of order and overwrite `latest` with an older image. SHA-tag deployment remains safe. `.github/workflows/ci.yml:82-90`

4.7 No immediate Docker build break is evident: the image imports the three critical packages and runs a real in-container verification before publishing. `Dockerfile:19-22`, `.github/workflows/ci.yml:66-69`

5. **Docs accuracy**

5.1 The deployed five-second claim is unproven and currently contradicted by the only attached deployed measurement: p95 28.1 seconds with 19 absorbed 429s. `README.md:38`, `README.md:136-137`, `docs/LOADTEST.md:47-50`

5.2 Release placeholders remain for URL, usability, deployed latency/throughput, and author text. `README.md:10`, `README.md:38-39`, `README.md:136-137`, `README.md:181-183`

5.3 README and SECURITY still say 40 megapixels; code and LIMITS enforce 25 megapixels. `README.md:193`, `docs/SECURITY.md:30`, `app/config.py:47`

5.4 README says accent differences in warnings become Needs review, but default ASCII decoding can erase them before comparison. `README.md:41`, `README.md:67-71`, `app/ocr/alphabet.py:46-51`

5.5 LIMITS says the recognizer handles Latin accents, then says default decoding suppresses them. `docs/LIMITS.md:53-54`, `docs/LIMITS.md:63-68`

5.6 SECURITY’s “`Server-Timing` on every response” is false for middleware early exits. `docs/SECURITY.md:36`, `docs/SECURITY.md:64`, `app/security.py:132-180`

5.7 SECURITY says the deployment mounts `/tmp` in memory, but the Azure commands configure no volume. `docs/SECURITY.md:14-19`, `docs/DEPLOY.md:46-53`

5.8 DEPLOY says no registry password is stored anywhere, after instructing that the ACR admin password be stored in GitHub secrets. `docs/DEPLOY.md:27-35`, `docs/DEPLOY.md:56-57`

5.9 README’s local “2.3 s / 2.6 s” no longer matches the published 2.451 s / 2.687 s figures. `README.md:38`, `README.md:135`, `docs/EVAL.md:7`

5.10 README says one sideways read caused the degraded issues, while EVAL records two `rotate90` issue verdicts. `README.md:133`, `README.md:143`, `docs/EVAL.md:46`

5.11 Browser-test documentation overstates assertions: scripts print crops, polygons, rows, export and filtering results but generally fail only on browser/HTTP errors; the photo verdict is explicitly unchecked. `tests/browser/README.md:3-5`, `tests/browser/smoke_single.py:22`, `tests/browser/smoke_batch.py:56-90`

6. **Tests to add, highest damage first**

6.1 `test_accented_print_cannot_produce_exact_warning_under_ascii_decode` — real decoder output or fixture proving the false-pass policy explicitly. `app/ocr/alphabet.py:46-51`

6.2 `test_large_jpeg_draft_preserves_original_canonical_dimensions_and_boxes` — exercise the actual draft branch, including EXIF. `app/pipeline/images.py:92-108`

6.3 `test_unparseable_net_contents_cannot_yield_ready` — pin `not_checked` verdict semantics. `app/pipeline/compare.py:173-176`, `app/pipeline/compare.py:252-255`

6.4 `test_multiple_equal_percent_statements_with_conflicting_proof_mismatch` and `test_wrapped_percent_and_proof_are_one_statement`. `app/pipeline/compare.py:93-156`

6.5 `test_zero_percent_warning_is_not_required` plus a browser assertion that the card says “Not required.” `app/pipeline/parsers.py:65-82`, `app/static/render.js:122-143`

6.6 `test_admission_limiter_releases_after_success_exception_and_cancellation` — also pin global cap and trusted-XFF selection. `app/security.py:67-115`, `app/security.py:151-177`

6.7 `test_changing_csv_or_images_clears_decisions_and_rebuilds_results` — prevent stale approvals. `app/static/batch.js:55-75`, `app/static/batch.js:118-120`

6.8 `test_csv_relative_path_disambiguates_duplicate_basenames` — cover real folder-aware pairing. `app/static/batch.js:92-99`

6.9 `test_every_early_middleware_response_has_server_timing` — extend the existing header test beyond CSP. `tests/integration/test_verify_api.py:166-178`

6.10 `test_slot_with_multiple_pending_runner_futures_releases_after_all_finish` — harden the pool abstraction against future concurrent use. `app/ocr/pool.py:146-164`

7. **Ship list**

7.1 **Must — S:** Restrict Ready to explicitly permitted absent fields; malformed required values must remain Needs review. `app/pipeline/compare.py:252-255`

7.2 **Must — M:** Repair large-JPEG canonical geometry and add the draft/EXIF regression test. `app/pipeline/images.py:83-108`

7.3 **Must — M:** Resolve D-032’s false-exact behavior—prefer disabling it by default, or explicitly abandon the physical “exact” claim and document the false-pass risk. Re-run evaluation with engine/alphabet metadata. `app/ocr/alphabet.py:23-51`, `docs/DECISIONS.md:40`

7.4 **Must — M:** Model alcohol statements across lines/images correctly, including proof conflicts and split percent/proof text. `app/pipeline/compare.py:93-156`

7.5 **Must — S:** Accept 0% for the Part 16 threshold and render `not_required` consistently. `app/pipeline/parsers.py:65-82`, `app/static/render.js:122-143`

7.6 **Must — S:** Clear decisions/metrics on rebuilt batch inputs and match exact relative CSV paths before basename fallback. `app/static/batch.js:55-120`

7.7 **Must — S:** Prevent ACR publishing unless the test job passes; remove proxy trust from the generic image. `.github/workflows/ci.yml:13-90`, `Dockerfile:27-29`

7.8 **Must — L:** Diagnose the deployed 28-second p95/429 behavior and satisfy the five-second gate, or state plainly that the gate failed. `docs/LOADTEST.md:47-50`

7.9 **Must — S:** Replace release placeholders and correct the 25 MP, timing-header, tmpfs, registry-password, accent, and latency claims. `README.md:10-193`, `docs/SECURITY.md:14-42`

7.10 **Can wait — M:** Add a fully locked, hash-pinned transitive dependency set; until then say “direct dependencies pinned.” `requirements.txt:1-24`

7.11 **Can wait — S:** Make early responses carry `Server-Timing`. `app/security.py:51-64`

7.12 **Can wait — S:** Harden `slot()` against multiple concurrent runner futures. `app/ocr/pool.py:146-164`

7.13 **Can wait — M:** Turn browser smoke output into functional assertions for crops, export, filters, duplicate folders, cache invalidation, and backoff. `tests/browser/smoke_batch.py:56-90`