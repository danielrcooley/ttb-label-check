# Dispositions for review 005 (real-label changes)

Each finding in `005-real-labels.response.md` was checked against the code before anything was
changed. Verdicts: **Accepted** (fixed as stated), **Partially** (fixed differently or in part, with
the reason), **Rejected** (with the reason), **Deferred** (true, not for this submission). The
fixing commit is the one that adds this file; the product decisions it records are D-039.

## 1. Bugs introduced by these changes

| # | Finding | Disposition |
|---|---|---|
| 1.1 | Exactness deleted every space, so "womens hould" passed as exact | **Accepted.** Exactness now compares the sequence of words and punctuation marks (`_tokens` in `warning.py`), ignoring letter case and spacing next to punctuation only. "womens hould", "acar" and "GOVERN MENT" are never exact (they are slips for a person: Needs review with the diff). Pinned by `test_word_boundary_changes_are_never_exact`. Verified first: the old `_literal_key` did `replace(" ", "")`. |
| 1.2 | `fold_company` drops corporate forms everywhere; "ACME LLC" and "ACME Inc." matched | **Partially.** Two different forms on the two sides ("LLC" against "Inc.", spelled one way so "Co." and "Company" agree) now send a bottler match to Needs review with both forms in the note (`company_forms`, `bottler_check`). An omitted form stays a match with the "Label says" note: that is what the real labels showed (D-035) and it is not a different entity. Address tokens ("CO" the state) are folded on both sides alike; the fuzzy matcher already tolerates that. Pinned by `test_bottler_with_a_different_corporate_form_is_review_not_match`. |
| 1.3 | Rescue outcome depended on server load (BusyError swallowed) | **Accepted, by design change.** Batch requests never rescue (see 3.6): every image is read exactly once on the request's own slot. Interactive rescue reads take their own slots with the interactive wait; a read that cannot get one is refused like any other interactive read (HTTP 429 with Retry-After), never skipped silently. The round is a function of the input and the configuration alone. Pinned by `test_batch_requests_read_every_image_exactly_once`. |
| 1.4 | First improving 90-degree span suppressed the 270 and full-resolution reads | **Accepted.** All the reads of the round run and the best span per image wins. Pinned by `test_rescue_is_one_round_across_the_workers_and_keeps_the_best_read` (90 reads one word wrong, 270 reads exactly, exact wins on two workers). Note the round is bounded (3.7), so with one worker only the first planned read runs; that is the budget, stated in the docs. |
| 1.5 | Images the rotation retry turned were excluded from the rescue | **Accepted.** The retry's losing reads are kept as `alternates` and the rescue looks there first, at no cost; a turned image then only has the full-resolution read left to plan. Pinned by `test_rotation_retry_reads_are_reused_before_any_rescue_read`. |
| 1.6 | Rescue slot wait missing from `queue_ms` | **Accepted.** Each rescue read adds its wait to the image's `queue_ms`. No test (needs contention); noted under 6.6. |
| 1.7 | Bottler evidence rebuilt in OCR order, duplicates possible | **Accepted.** `_as_printed` rebuilds evidence and the found text in the candidate's order, each line once; used by the origin check too. |
| 1.8 | Whole-image median thickness as the column tolerance | **Deferred.** Half the median line thickness is tens of pixels; separate body columns sit hundreds apart. Noted in LIMITS as a known approximation; 7.8. |
| 1.9 | `group.index(head[-1])` finds the first equal line | **Accepted.** Identity, not equality. |
| 1.10 | Mixed-orientation boxes could be joined by horizontal overlap | **Accepted, and it was live.** The fake-engine test for the new round showed it: the strips of a sideways statement crossing an upright label's brand line were spliced with it. A vertical strip and a horizontal line are now never one column, and a rescued statement replaces whatever the kept read had in the same place (`_adopt`). |
| 1.11 | No coordinate or slot leak found | Noted. |

## 2. False passes and false alarms

| # | Finding | Disposition |
|---|---|---|
| 2.1 | "womens hould" exact | **Accepted** (1.1). |
| 2.2 | Different legal entities pass after folding | **Partially** (1.2). |
| 2.3 | "women" to "woman" is review, not an issue | **Rejected as a change; accepted as a doc fix.** The tool cannot tell a misprint from a small-print slip in an image; the rule in AGENTS.md is that a heuristic finding is Needs review, never a pass and never a fail. The diff names the word. The docstring that called "WOMAN" small print was wrong and is corrected; D-037 already says the label genuinely prints it. |
| 2.4 | A bare inserted number is always noise | **Rejected.** A lot code or a year set against the statement is common on real labels (the hand-checked ale); an extra number printed inside the statement is not a plausible deviation, and the diff still shows it. |
| 2.5 | A different brand at 80-89 softens an issue to review | **Rejected.** Review is the designed outcome for an uncertain read; the crop is shown. D-035 records the evidence. |
| 2.6 | A trailing hyphen added by OCR merges two words | **Rejected as a false alarm.** "duringpregnancy" against "during pregnancy" is classified noise (the merged-word rule), so Needs review with a diff, not an issue. |
| 2.7 | 90-degree partial suppresses an exact 270 | **Accepted** (1.4). |
| 2.8 | Inflated tolerance interleaves columns | **Deferred** (1.8). |
| 2.9 | The "exact" note was untrue while boundary changes passed | **Accepted** (1.1). The case decision itself stands: the regulation regulates capitals for the heading only, which is checked separately. |

## 3. Latency against the five-second requirement

| # | Finding | Disposition |
|---|---|---|
| 3.1-3.5 | Pass counts and the cases that miss the target | **Accepted; measured.** On the deployed build at af9e239 a single-image request cost 8.6 s median (four reads) against 2.0 s before (docs/LOADTEST.md). New policy: the rescue is one round of at most one read per worker, in parallel, interactive only. A front-only upload on two workers costs the upright read plus one read-time; a pair without a statement the same (each image gets its first planned read). Measured after deployment; numbers in the README. |
| 3.6 | The batch screen's one-image extracts pay the rescue before pairing | **Accepted.** This was the largest effect: batch throughput fell to a quarter. Batch requests never rescue; "each image is read once" is true again and the batch sheet says what that means for a statement printed sideways. |
| 3.7 | Ranked mitigations | Chosen: a bounded parallel round (the reviewer's #5 with a hard bound instead of a clock) plus batch exclusion (#2). Not chosen: disabling the rescue (#1: the vertical-statement labels are real and were the point of D-035); removing the full-resolution read (#3: kept, but it is planned first only when the heading was seen); a clock budget (#4: a clock makes the verdict depend on the machine's speed; a bound on reads does not). |

## 4. Evaluation tooling and claims

| # | Finding | Disposition |
|---|---|---|
| 4.1-4.5 | `cola_fetch.py` politeness, caps, resumption, output containment, error paths | **Deferred (7.9).** The tool is documented as a one-off, was run once with the defaults, and stays out of the product. The docstring now states the caps as they are. |
| 4.6 | Registry use defensible; no provenance beyond the URL | Noted. EVAL_REAL.md names the registry, the window, the delay and the caps. |
| 4.7 | Aggregates computed as described | Noted. |
| 4.8 | "Present" counts any anchored span | **Accepted as wording.** EVAL_REAL.md now says "statement located (heading found)"; the exact / slips / wording split is the accuracy. |
| 4.9 | Origin check is a proxy | **Accepted as wording.** Stated in EVAL_REAL.md. |
| 4.10 | Read rates parse the concatenation of all lines | **Accepted as wording.** Stated in EVAL_REAL.md. (The product's extract-only fields do the same and say so.) |
| 4.11 | p95 index one rank low; latency excludes decode | **Accepted.** Nearest-rank p95 in both evaluators. Latency covers the service call, which includes decoding; the file read and pre-fit are outside it, stated. |
| 4.12 | Both "absent" records were claimed to lack a statement | **Accepted; the claim was wrong.** The builder opened the second record's image: the statement is printed vertically along the right edge in small type and the sideways read could not read it at 1,225 pixels. EVAL_REAL.md's hand-check and the README now say so. |

## 5. Docs accuracy

| # | Finding | Disposition |
|---|---|---|
| 5.1 | README deployed latency predates the rescue | **Accepted.** Re-measured on the new build after deployment (README "Measured", LOADTEST.md). |
| 5.2 | README degraded results stale | **Accepted.** Updated from the regenerated EVAL.md. |
| 5.3 | "character for character", "each image read once" | **Accepted.** Exactness is described as it is; the batch claim is true again and says what it excludes. |
| 5.4 | Test counts | **Accepted.** |
| 5.5 | LIMITS overstates the reads and understates the cost | **Accepted.** Rewritten for the bounded round, with the cost in read-times. |
| 5.6 | REQUIREMENTS_TRACE "about five seconds" and the exactness wording | **Accepted.** States the cases that exceed the target and what exactness ignores (case, spacing next to punctuation, quote style, hyphenated line breaks). |
| 5.7 | EVAL.md degraded p95 and rotated median exceed five seconds | Noted; those are the three-read rotation retry for sideways photographs, stated in EVAL.md and LIMITS. |
| 5.8 | Regeneration timestamp before the fetch date | **Accepted.** The fetch date was wrong by a day (the fetch ran late on 2026-09-03 local time). |
| 5.9 | D-035 overclaims | **Accepted.** Reworded; the re-read policy is D-039. |
| 5.10 | D-037 contradiction | **Partially.** D-037 already says the tequila label genuinely prints "WOMAN" and that review is the right answer; the contradiction was in `warning.py`'s docstring, corrected. |
| 5.11 | Older decisions describe the removed "case" assessment | **Accepted.** D-023 and D-029 carry a superseded-by note. |
| 5.12 | `normalize.py` docstring | **Accepted.** |
| 5.13 | No live threshold-90 claim | Noted. |

## 6. Tests

6.1, 6.2, 6.3, 6.4, 6.5 added (see section 1). 6.6 and 6.7 deferred (need contention or
cancellation harnesses; the pool's own tests cover release-after-inference). 6.8 deferred with 1.8.
6.9 deferred (the order is now the candidate's by construction). 6.10 and 6.11 deferred with 7.9.

## 7. Ship list

7.1 done (1.1). 7.2 and 7.3 done as the bounded round plus batch exclusion (3.7). 7.4 done in part
(1.2). 7.5 done: re-measured after deployment. 7.6 done (section 5). 7.7 done (1.6, 1.7).
7.8, 7.9, 7.10 deferred and recorded in LIMITS.
