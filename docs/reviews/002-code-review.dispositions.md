# Dispositions for review 002 (code review by Codex, 2026-09-04)

Reviewer: Codex (gpt-5.6, high reasoning), repository snapshot at a4d4290 supplied inline
(114k tokens). Builder: Claude Code. Decision-maker: Daniel R. Cooley.
Fixes for every accepted item below landed in commit b473b22 unless the row says scheduled.
Legend: **Accepted** (fixed or scheduled), **Partially**, **Rejected**
(reason), **Deferred** (backlog, after submission).

The review found two defects that undercut proofs I had been relying on, both accepted and fixed
first: literal backspace bytes in the origin regex (1.10) and a CI container check that could not
fail (found while investigating; see D-028 in the decision log).

## 1. Bugs
| # | Finding | Disposition |
|---|---|---|
| 1.1 | Pool releases capacity on client cancellation while the OCR thread keeps running | **Accepted.** The slot is now released only when the executor job finishes, even if the awaiting request was cancelled; a cancelled request counts against capacity until its inference ends. |
| 1.2 | Batch multi-image admission is not atomic; a slot can be lost between images | **Accepted.** Batch requests now reserve one slot once and run all their images through it sequentially; a contended test with a concurrent request covers it. |
| 1.3 | Missing required alcohol statement in the application still yields Ready | **Accepted.** When the statement is required for the beverage type and the application omits it, the check is Needs review, never info. |
| 1.4 | Proof ignored when percentages agree | **Accepted.** When both sides state proof and they disagree, the check is a mismatch; a label that omits proof while the application states it stays a match (proof is optional on labels). |
| 1.5 | First parseable alcohol line used, not the best | **Accepted.** The line whose value matches the application wins; otherwise the first line. |
| 1.6 | Accent-stripping makes "alcoholič" exact | **Accepted, reversing my own fix.** Exact means exact. An accented letter in the read is now "noise" (Needs review). The evaluation reports the resulting false alarms honestly instead of hiding them. |
| 1.7 | Anchor detection accepts "WARNING" alone | **Accepted.** Both words are required (each fuzzy-matched separately). |
| 1.8 | Warning span ignores layout boundaries | **Accepted.** Continuation lines must overlap the anchor line horizontally. |
| 1.9 | 0.5% threshold not applied | **Accepted.** If the application states under 0.5% alcohol, the warning is reported as not required. |
| 1.10 | Backspace bytes in the origin regex | **Accepted.** Fixed; unit test for extract-only mode added. Root cause: shell backslash handling on this machine; all later edits went through script files. |
| 1.11 | Batch drops duplicate basenames silently | **Accepted.** Files are keyed by relative path when the browser provides one; duplicate basenames are reported in the intake summary. |
| 1.12 | Stale items after inputs change | **Accepted.** Items are rebuilt whenever images or the CSV changed since the last build. |
| 1.13 | CSV image lists with missing files silently accepted | **Accepted.** Missing listed files are reported per row and the method label is accurate. |
| 1.14 | Crop code scales through an orientation mismatch instead of verifying | **Accepted.** Crops are skipped when bitmap and canonical dimensions disagree (other than a pure swap), and the mismatch is noted. |

## 2. Security
| # | Finding | Disposition |
|---|---|---|
| 2.1 | Admission after multipart parsing | **Accepted.** The per-client cap and a new global in-flight request cap are enforced in middleware before the body is parsed for the upload endpoints. |
| 2.2 | Parts between the spool threshold and the request cap can touch disk | **Partially.** The honest fix without a custom parser is a lower request cap (6 x 10 MB is the real maximum) and tmpfs for `/tmp` in the deployment; SECURITY.md now says exactly what happens rather than claiming "never". |
| 2.3 | `/compare` unmetered | **Accepted.** Per-item line and text-length limits in the schema; the endpoint is covered by the same middleware caps. |
| 2.4 | `X-Forwarded-For` spoofable | **Accepted.** With proxy trust on, the rightmost value (appended by the trusted proxy) is used; documented for Azure Container Apps. |
| 2.5 | `int(Content-Length)` can raise | **Accepted.** Malformed length returns 400. |
| 2.6 | Early 411/413 responses lack security headers | **Accepted.** Headers applied to every response, including early returns. |
| 2.7 | XSS and CSV-injection handling are fine | Noted. |

## 3. Robustness under stress
| # | Finding | Disposition |
|---|---|---|
| 3.1 | Many clients can complete parsing before admission | **Accepted** via 2.1 (global in-flight cap in middleware). |
| 3.2 | 40 MP decode is ~120 MB per image | **Accepted.** Pixel cap lowered to 25 MP; JPEG draft-mode decoding reduces memory before conversion. |
| 3.3 | Cancellation does not cancel inference | **Accepted** via 1.1 (capacity stays held until the thread finishes). Cancelling the thread itself is not possible with ONNX Runtime; documented. |
| 3.4 | Table rebuild is quadratic at 1,000 items | **Accepted.** Rebuilds are coalesced (at most a few per second) and the sort is over a precomputed severity key. |
| 3.5 | Detail panel re-rendered on every completion | **Accepted.** The rendered panel is cached per item and reused. |
| 3.6 | Backoff sleeps while holding a slot | **Accepted.** The slot is released before sleeping. |
| 3.7 | No body-read timeout for slow uploads | **Partially.** Uvicorn keep-alive timeout is set; slow-loris protection is the ingress's job on Azure Container Apps and is documented. |
| 3.8 | Pause is not immediate | **Accepted as documented behavior.** The button says "Pause"; in-flight reads finish. |

## 4. Code quality
| # | Finding | Disposition |
|---|---|---|
| 4.1 | Eval counts unassessed defects as detections | **Accepted.** Tiny and all-bold are reported as "not assessed by design"; the detection rate covers the four assessable defects. README wording updated. |
| 4.2 | Batch concurrency test tests the wrong condition | **Accepted.** Replaced by a contended test (see 1.2). |
| 4.3 | Exact-warning test enshrines a false pass | **Accepted** via 1.6. |
| 4.4 | Eight EXIF orientations not tested | **Accepted.** Parametrized test over orientations 1 to 8. |
| 4.5 | Browser tests not in the repository | **Accepted.** The Playwright smoke scripts live in `tests/browser/` with instructions; they need a local server and a browser, so they are not part of CI. |
| 4.6 | `review_similarity` unused | **Accepted.** Parameter and setting removed. |
| 4.7 | Dead `original` variable | **Accepted.** Removed. |
| 4.8 | Response request id differs from the header | **Accepted.** The middleware id is reused in the body. |
| 4.9 | Docs say bulk compare; UI sends singletons | **Accepted as a docs fix.** The UI compares each application as it completes (that is the streaming design); the bulk endpoint serves scripted clients. |

## 5. Requirements gaps
| # | Finding | Disposition |
|---|---|---|
| 5.1 | Five-second gate not enforced | **Accepted.** The gate is measured on the deployed host (interactive front+back p95 under concurrent batch load) with `tools/loadtest.py --endpoint verify --interactive`; the number goes in the README. The local CI threshold stays loose because runner speed varies. |
| 5.2 | Usability evidence is a placeholder | **Accepted.** Scheduled with the author before submission. |
| 5.3 | No 300-item evidence | **Accepted.** A 300-image browser batch run and a 300-request steady load test are recorded before submission. |
| 5.4 | Batch unsafe for realistic folders | **Accepted** via 1.11 to 1.13. |
| 5.5 | Exactness weakened by normalization | **Partially.** Accent removal reverted (1.6). Whitespace collapse and typographic-quote unification remain, because line wrapping and curly quotes are rendering, not wording; both are stated in the docs. Single-character differences are Needs review, never a pass. |
| 5.6 | Bottler omitted still yields Ready | **Partially.** A "not compared: not provided in the application" row is always shown for bottler and origin so the omission is visible; the verdict stays Ready because the tool cannot compare what it was not given, and forcing Needs review on every quick check would recreate Dave's phone-system problem. Bottler moved out of the optional accordion. |
| 5.7 | Batch privacy sentence inaccurate | **Accepted.** Reworded to what actually happens. |

## 6. Docs accuracy
All eleven accepted: cooperative-budget claim removed; spool behavior stated accurately; global
in-flight cap added so the memory-bound statement is true; `Server-Timing` header added so the
timing-header statement is true; "provider interface" reworded to the engine interface that exists;
bulk-compare wording fixed; unpaired thumbnails wording fixed; README warning wording fixed;
placeholders are release blockers tracked in NOTES; the 503-until-warm behavior stated; the
REGULATIONS.md table corrected to say bold, body weight, contrast and size are not checked in this build.

## 7. Top five
All five accepted and scheduled ahead of deployment, in the reviewer's order.

## Pushed back, for the record
- 5.6: verdict stays Ready when optional comparison data is absent (visible "not compared" row instead).
- 2.2: no custom multipart parser; honest documentation plus a tighter request cap and tmpfs.
- 3.7: slow-client protection left to the ingress, documented.
