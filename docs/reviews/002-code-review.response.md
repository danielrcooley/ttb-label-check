## 1. Bugs

1. `app/ocr/pool.py` releases capacity when an awaiting request is cancelled, although `run_in_executor` does not stop the underlying OCR thread: `"lines = await loop.run_in_executor(...)"` followed by unconditional `"_active -= 1"` and `"_sem.release()"`. Client disconnects/cancellation can therefore admit more OCR work than `workers`, hide executor queueing from `queue_ms`, and accumulate unstoppable jobs.

2. Batch multi-image admission is not atomic. `app/services.py` says a request must “never be refused halfway through,” but executes `"[await process_image(... interactive=False) for ...]"`; each image releases and reacquires the pool slot. Another request can take the slot between images, causing a 429 after earlier images were already processed. `tests/integration/test_batch_mode.py` tests only an uncontended request and cannot catch this race.

3. Required alcohol information can produce a ready verdict when missing from the application. In `app/pipeline/compare.py`, when a spirits application omits alcohol but the label contains it, the code returns `"status=Status.info"`. `_verdict()` accepts `Status.info`, so the response can be `"ready_for_approval"` despite an uncheckable required application field.

4. Alcohol comparison ignores proof when percentages agree. `app/pipeline/parsers.py` defines `Alcohol.proof`, but `"return abs(app.percent - label.percent) <= tolerance"` compares only percent. Application `45% (80 Proof)` versus label `45% (90 Proof)`, or application `45% (90 Proof)` versus label `45%` can incorrectly be Match.

5. `_alcohol_check()` uses the first parseable line, not the best or application-matching statement: `"for ln in lines: ... if got: found ... break"`. A preceding line such as `Contains 5% alcohol flavoring` makes a correct later `45% ALC/VOL` appear mismatched.

6. The warning is not truly exact. `app/pipeline/warning.py` removes accents before setting `exact`: `"strip_diacritics(s)"`. The test explicitly treats `alcoholič` as exact. A genuinely accented or altered printed word can therefore yield `"Wording is exact"` instead of Needs review, contrary to the emphasized word-for-word requirement.

7. Warning anchor detection accepts fragments. `"_anchor_score"` uses `fuzz.partial_ratio`, so a standalone `WARNING` can score as a perfect substring of `GOVERNMENT WARNING`. `find_warning()` then reports a warning as present and differently worded rather than absent.

8. Warning span construction ignores layout boundaries. `app/pipeline/warning.py` appends every later flattened line with `"for nxt in group[i:]"`; on columns or nearby unrelated text, interleaved lines can truncate or corrupt the warning after two similarity declines.

9. Warning applicability ignores the statutory 0.5% threshold. `compare()` always calls `build_report()`, whose absent message says it applies at 0.5% or more, but no ABV-dependent branch exists. A valid sub-0.5% product is incorrectly given an issue for no warning.

10. `app/pipeline/extract.py` contains literal backspace characters instead of word-boundary escapes: `r"(product of|...|country of origin)"`. Normal label text will not match, so extract-only batch results generally return empty `origin_lines`.

11. Batch files collide by basename. `app/static/batch.js` reduces every file to `"name.split(/[\\\\/]/).pop().toLowerCase()"` and silently keeps only the first with `"if (!state.images.has(key))"`. Selecting folders containing repeated `front.png` or `back.png` drops applications without warning.

12. Batch input changes can leave stale work items. `start()` rebuilds only when `"!state.items.length || state.items.every((i) => i.status === 'done')"`. After an error or `no-images` row, adding a corrected CSV or more images and pressing Resume continues the old pairing instead of rebuilding it.

13. Explicit CSV pairing silently accepts incomplete lists. `"row.images.map(norm).filter((n) => files.has(n))"` discards missing listed files without reporting them. If any listed file exists, filename-prefix fallback is skipped, and `"method: row.images.length ? 'listed in CSV'"` can falsely claim the explicit list was honored.

14. The browser crop code does not perform the promised orientation-dimension verification. `app/static/render.js` merely computes `"const sx = bmp.width / im.width, sy = bmp.height / im.height"` and scales through disagreement. There is no fallback, so an EXIF-decoding mismatch can produce a wrong evidence crop.

## 2. Security

1. Upload limits and per-client admission run after multipart parsing. FastAPI creates `UploadFile` objects before entering `"async with limiter.slot(request)"`; hostile clients can force framework buffering and multipart work before either the six-image check or per-client limit applies.

2. Oversized image parts can touch disk despite the no-storage claim. `app/main.py` sets `"MultiPartParser.spool_max_size = settings.max_image_bytes + 1024 * 1024"`. A 12–39 MB part is spooled after roughly 11 MB and only later rejected by `_read_uploads()` at 10 MB.

3. `/api/v1/compare` is an unmetered CPU endpoint. Its body is parsed before `"if len(body.items) > settings.max_compare_items"`, it does not use `ClientLimiter`, and `CompareItem.lines` has no count or text-length limit. A 40 MB body containing many OCR lines can drive repeated span generation and fuzzy matching without touching OCR admission control.

4. Azure proxy trust is spoofable unless ingress strips incoming forwarding headers. `ClientLimiter.client_id()` trusts `"fwd.split(',')[0]"`; with `TTB_TRUST_PROXY=true`, a caller can vary the first `X-Forwarded-For` value to bypass the per-client cap.

5. `Content-Length` parsing is unsafe: `"if int(length) > self.settings.max_request_bytes"`. A malformed or excessively long numeric value raises `ValueError`, producing a 500 rather than a controlled 400.

6. Early 411/413 responses return before security headers are attached. Both `"return error_response(...)"` branches precede the code adding CSP, `nosniff`, referrer, and cache headers.

7. The frontend’s user/OCR rendering is otherwise XSS-conscious: text uses `textContent`; the sole `innerHTML` assignment is the bundled same-origin SVG sprite. Common CSV formula prefixes are also neutralized by `"if (/^[=+\\-@\\t\\r]/.test(s))"`.

## 3. Robustness under stress

1. Fifty clients can each complete multipart buffering before admission, while six-image interactive requests create multiple OCR waiters per request. The only global bound is the OCR semaphore, not request memory or queued coroutines.

2. Accepted images can consume far more memory than their upload size. `decode_image()` allows 40 megapixels and executes `"im = im.convert('RGB')"` before downscaling; that is roughly 120 MB per image. Six images are decoded concurrently by interactive `asyncio.gather`, and multiple clients can push a 4 GiB container toward OOM.

3. Cancellation does not cancel inference, as described in §1.1. Repeated slow-client disconnects can fill the executor with work while the semaphore reports free capacity.

4. The browser’s 1,000-image path grows poorly. `renderTable()` sorts all items and rebuilds the table after every completion via `"processItem(...).finally(() => { ... renderTable(); ... })"`, producing roughly quadratic UI work. `state.extractions` also retains every full OCR response, while item state duplicates line/image objects.

5. Expanding a detail row during a running batch repeatedly starts asynchronous crops and figure rendering whenever the table is rebuilt. `"renderDetail(panel, it)"` is invoked on each completion, even though the previous panel has been detached.

6. Backoff holds a browser request slot while sleeping. In `extractOne()`, `"await new Promise(...setTimeout...)"` occurs inside the `try`, before `finally { releaseSlot(); }`. Several 429s can leave all nominal slots sleeping and stall queued work.

7. Slow uploads have no application-level body-read timeout and are not counted by `ClientLimiter` until parsing finishes. The platform must supply slow-client protection; the code does not.

8. Refresh discards the batch, as documented. Pause is also not immediate: already-started `processItem()` calls and non-cancellable server OCR may continue after `AbortController.abort()`.

## 4. Code quality

1. The evaluation counts undetected defects as detections. `tools/evaluate.py` defines `"tiny": lambda r: r.warning.present and r.warning.exact` and the same for `"allbold"`, then reports them in `"Detection rate"`. Those predicates prove the defect was not assessed, making the published 6/6 metric misleading.

2. The batch concurrency regression test tests the wrong condition. `test_two_image_batch_verify_succeeds_on_a_single_worker` has no competing request or waiting interactive job, so it cannot verify “never refused halfway.”

3. The exact-warning suite enshrines a false pass: `"assert r.exact"` for text changed to `alcoholič`. It should assert Needs review if “exact” is the user-facing/legal status.

4. Accepted coordinate-test scope was not implemented. `tests/unit/test_images.py` checks one EXIF orientation and rotation point mappings, not all eight EXIF orientations or browser/server agreement promised by review 001.

5. No supplied browser test covers batch pairing, repeated filenames, pause/resume, CSV export, keyboard behavior, or memory. README lists Playwright as a tool, but `requirements-dev.txt` contains no Playwright dependency and the snapshot contains no browser tests.

6. `"review_similarity"` is accepted by `build_report()` but never used. `Settings.warning_review_similarity` and the `REVIEW` test constant therefore imply threshold behavior that does not exist.

7. `app/pipeline/compare.py` creates and deletes unused dead state: `"original = {id(ln): ln for ln in stripped}"` followed by `"del original"`.

8. Success responses use a different request ID from the response header. Middleware creates `request.state.request_id`, while services call `"new_request_id()"`; this weakens operational correlation.

9. Batch documentation says comparisons are bulk, but `processItem()` sends singleton calls: `"compare([{ item_id: item.key, ... }])"`. The 100-item API contract is unused by the UI.

## 5. Requirements gaps

1. The five-second gate is not enforced. `tests/integration/test_verify_api.py` permits `"total_ms < 15000"`, and no committed test measures deployed front/back p95 under concurrent batch load. `docs/EVAL.md` already reports degraded p95 `6286 ms`.

2. The novice-usability evidence remains a placeholder: README says `"Observed usability test: _USABILITY_RESULT_"`. The “my mother could figure out” requirement is still asserted from design features, not demonstrated.

3. The claimed 200–300-item batch evidence is absent. `docs/REQUIREMENTS_TRACE.md` says `"Tested at hundreds of images"`, but the largest committed steady run in `docs/LOADTEST.md` is 40 extract requests.

4. Batch handling is unsafe for realistic folder structures because duplicate basenames are silently discarded, incomplete CSV image lists are not reported, and edited inputs can reuse stale pairings. This weakens the emphasized batch requirement despite the polished demo path.

5. Word-for-word warning exactness is weakened by accent removal, whitespace repair, typographic normalization, and the rule that any one-character change in a word of five or more letters is `"noise"`. At minimum those cases must be Needs review, never `exact`.

6. Bottler/producer can be omitted entirely and still yield Ready. `compare()` only adds that mandatory-element check under `"if app.bottler:"`; the UI hides it under `"More fields (optional)"`.

7. The batch-page privacy statement is false. `app/static/index.html` says `"Nothing leaves your browser except the images being read, one at a time."` The CSV is uploaded to `/csv/parse`, application rows go to `/compare`, and up to four image requests run concurrently.

## 6. Docs accuracy

1. `docs/SECURITY.md` claims `"Cooperative time budgets"`, but `app/services.py` has no deadline or pass-budget check. A recognition call can run indefinitely.

2. `docs/SECURITY.md` says `"images are never written to disk"`. Parts above the approximately 11 MB spool threshold can be written before the route rejects them at 10 MB.

3. The same document says total memory is bounded by request size times concurrent requests, but admission occurs after parsing, is only per client, and `/compare` bypasses it. There is no global concurrent-request bound.

4. `docs/SECURITY.md` promises `"the per-request timing header"`, but middleware adds no timing header; timing exists only in successful verification JSON.

5. `docs/APPROACH.md` says `"A provider interface exists for an optional second opinion"`, but no such interface appears in the repository snapshot.

6. `docs/APPROACH.md` says applications are `"compared in bulk"`; the browser sends one-item `/compare` requests.

7. `docs/LIMITS.md` says `"thumbnails are created only when a row is expanded"`. `renderUnpaired()` creates an image and object URL for every unpaired file at once.

8. README’s warning claim, `"a changed or missing word is a mismatch"`, contradicts `_same_word_modulo_noise()`, which classifies one-edit replacements in words of at least five characters as noise.

9. README still contains release-blocking placeholders: `"_DEPLOY_URL_"`, `"_DEPLOY_P95_"`, `"_DEPLOY_LATENCY_"`, `"_DEPLOY_THROUGHPUT_"`, `"_USABILITY_RESULT_"`, and `"_AUTHOR_SECTION_"`.

10. README says `"The first request after start waits for the models to load"`, but `_pool()` returns HTTP 503 until warm-up completes.

11. `docs/REGULATIONS.md` says bold, body weight, contrast, and relative size are checked, while `build_report()` always sets `"anchor_bold=Status.not_checked"` and `"body_not_bold=Status.not_checked"` and performs no contrast or size analysis.

## 7. Top five

1. Move multipart/request admission ahead of body parsing, enforce part count and byte limits during parsing, and set the spool threshold at or below the actual rejection boundary. This prevents the easiest memory/disk embarrassment on a public URL.

2. Make OCR cancellation and batch admission correct: do not release capacity until the executor job actually finishes, and reserve a multi-image batch request atomically or process it through an explicit request-level reservation.

3. Fix verdict correctness before tuning OCR: missing required application alcohol/bottler data must not be Ready; compare proof when supplied; select the relevant alcohol statement; apply the 0.5% warning threshold; never label altered OCR text `exact`.

4. Repair and test the real batch workflow: preserve relative paths or detect duplicate basenames, report every missing CSV-listed image, rebuild pairing when inputs change, release slots before backoff, and run a genuine 300-item browser/load test.

5. Make the evidence honest before deployment: correct the fake all-bold/tiny “detections,” add contested concurrency/browser tests, remove unsupported claims, and replace every README deployment/usability placeholder.