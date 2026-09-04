# Dispositions for review 004 (late-session changes, Codex, 2026-09-04)

Scope: everything after review 002 (79e9e04..009a407). The bundle was built after the first
deployed load test had appended its entries to `docs/LOADTEST.md`; those entries (p95 28 s, 19
refusals) came from a misconfigured replica (see 2.6) and were removed before the corrected runs.
Fixes landed in the commit that adds this file, unless a hash is given.

## 1. Bugs

| # | Finding | Disposition |
|---|---|---|
| 1.1 | ASCII masking could turn genuinely accented warning text into the required spelling and pass it as exact | **Accepted as a documented consequence, not changed.** The alphabet restriction is the author's decision (D-032) and stays on by default. The false-pass direction is now stated in LIMITS.md item 11, README (error analysis) and the module docstring. The switch `TTB_OCR_ASCII_ALPHABET` is documented. |
| 1.2 | Any `not_checked` check allowed Ready, including an uninterpretable required net-contents value | **Accepted, fixed.** `_verdict` allows `not_checked` only for bottler and country of origin (the fields the application may omit). An uninterpretable net-contents value is now Needs review with a note to compare by eye. Imported-without-origin is Needs review. Pinned by `test_unparseable_required_field_blocks_ready_and_omitted_optional_fields_do_not`. |
| 1.3 | Candidates compared only by rounded percent; equal percents with conflicting proofs could pass | **Accepted, fixed.** Proofs are collected across candidates; more than one distinct proof is a mismatch (same rule as percents). Test `test_equal_percents_with_conflicting_proofs_are_a_mismatch`. |
| 1.4 | A proof printed on its own line was treated as a second, derived percent, so a wrapped "45% / (80 Proof)" became "the label contradicts itself" | **Accepted, fixed.** `Alcohol.derived` marks a percent computed from a proof-only statement; derived values do not count as competing percents and the proof is joined to the chosen percent statement, so the inconsistency is assessed as one statement (Needs review, or mismatch when the application's proof differs). Tests `test_wrapped_percent_and_proof_lines_are_one_statement`, `test_proof_only_statement_still_matches_the_application`. |
| 1.5 | 0% could not parse, so a 0.0% product did not get the under-0.5% exemption | **Accepted, fixed.** Zero is accepted for percent (not for proof). Test `test_zero_percent_parses_and_exempts_the_warning`. |
| 1.6 | JPEG `draft()` changed the size reported as canonical; large-JPEG crops skipped | **Accepted; found independently and fixed in 59a583d (D-033)** before this response arrived. The draft target is now the working size, so the reduced decode actually engages for phone photos; two unit tests. |
| 1.7 | Rebuilding batch items kept old decisions; a failed replacement CSV did not bump `inputVersion` | **Accepted, fixed.** `buildItems` clears decisions and timings when the inputs changed since the last build; the CSV error path increments `inputVersion`. |
| 1.8 | `not_required` not rendered: card said "No warning statement found", batch list said "Warning: missing", summary said "the warning is exact" | **Accepted, fixed.** The card shows "Not required at this alcohol content" (info or not-checked tag), the batch issue list skips the warning, and the Ready summary says no statement is required below 0.5%. |
| 1.9 | Crop bounds combined evidence from several images while decoding only the first | **Accepted, fixed.** A crop uses only the evidence on the image it is cut from. |
| 1.10 | Folder-relative paths in the CSV could not disambiguate duplicate basenames | **Accepted, fixed.** A listed value is matched against the file's relative path first (exact, or as a path suffix, either slash style), then by basename. |
| 1.11 | Early middleware responses lacked `Server-Timing` | **Accepted, fixed.** Every early return carries it; the integration test for early rejections asserts it. |
| 1.12 | No pool leak; concurrent runner futures would release early | **Noted.** Callers are sequential by construction; hardening deferred (7.12). |

## 2. Fidelity to review-002 dispositions

| # | Finding | Disposition |
|---|---|---|
| 2.1 | 0% unparseable | Fixed (1.5). |
| 2.2 | Decisions survive rebuild; failed CSV unversioned | Fixed (1.7). |
| 2.3 | Crop guard skips every mismatch; draft created mismatches | **Partially accepted.** The draft mismatch is fixed (1.6). The guard still refuses any size disagreement rather than attempting a swap: a wrong crop is worse than none, and after 1.6 the only remaining cause is a browser/server EXIF disagreement, which the guard is for. |
| 2.4 | SECURITY said the deployment mounts `/tmp` in memory | **Accepted, docs fixed.** SECURITY.md now distinguishes the local `--tmpfs` recipe from the Azure ephemeral disk. |
| 2.5 | Slow-body timeout not stated as delegated | **Accepted, docs fixed.** SECURITY.md states that slow-client protection is the ingress's job. |
| 2.6 | README placeholders; deployed p95 28 s | **Resolved.** The 28 s run was against a replica that a probes-only YAML update had reset to 0.5 vCPU / 1 GiB with no environment variables. Resources restored; runbook and deploy script now carry the full container spec (59a583d). Corrected numbers: one client p95 3.1 s, two concurrent clients p95 5.9 s, zero refusals; placeholders for deployed latency and throughput filled. URL, usability and author sections are the author's, due before submission. |
| 2.7 | Usability evidence placeholder | **Open by design**: the author's observed test on Saturday. |
| 2.8 | `not_checked` broader than authorized | Fixed (1.2). |
| 2.9 | `Server-Timing` on early responses | Fixed (1.11). |

## 3. Alphabet restriction (D-032)

| # | Finding | Disposition |
|---|---|---|
| 3.1 | Blank index assumed | **Accepted, fixed.** The wrapper refuses a class list that does not start with `blank` (verified against rapidocr 3.9.2: 18,710 classes, `blank` at 0, one occurrence). |
| 3.2 | Unexpected shape silently restored full decoding | **Accepted, fixed.** Any shape other than (batch, time, classes) raises; the warm-up would fail and `/health` would report it. |
| 3.3 | Sign heuristic for probabilities vs logits | **Accepted, tightened.** Probabilities are recognized only when every value is within [0, 1]; anything else is treated as logits. |
| 3.4 | Confidence not renormalized | **Accepted, fixed.** Probabilities are renormalized over the allowed classes per timestep, so downstream confidence is P(class given the alphabet). Transcripts are unchanged (argmax is invariant); the evaluation was re-run. |
| 3.5 | Library attribute reliance | **Accepted as is.** A missing `text_rec`, `postprocess_op` or `character` raises at engine construction, which the warm-up surfaces; the version is pinned. |
| 3.6 | Batch ordering sound | Noted. |
| 3.7 | Docs not honest enough about what masking does and the false-pass direction | **Accepted, docs fixed** (LIMITS item 11, README, module docstring). |
| 3.8 | Evaluation does not record engine/alphabet metadata | **Accepted, fixed.** `docs/EVAL.md` now carries the engine, alphabet, model hashes and worker count. |

## 4. CI, Dockerfile, requirements, deployment

| # | Finding | Disposition |
|---|---|---|
| 4.1 | Container job could publish while tests fail | **Accepted, fixed.** `needs: test`. |
| 4.2 | Image forced `TTB_TRUST_PROXY=true` | **Accepted, fixed.** Removed from the image; it is set in the Azure deployment where the trusted ingress is. |
| 4.3 | `--no-deps` list is an upgrade hazard; no transitive lock | **Accepted, docs fixed; lock deferred** (SECURITY.md says "direct dependencies pinned" and lists the hash lock under deliberate omissions). |
| 4.4 | Audit cannot fail CI | **Kept, documented as deliberate** in SECURITY.md. |
| 4.5 | Admin credentials in CI secrets vs "no password stored anywhere" | **Accepted, docs fixed** (DEPLOY.md). |
| 4.6 | `latest` could be overwritten by an older run | **Accepted, fixed.** Workflow-level concurrency group per branch, never cancelled. |
| 4.7 | No build break | Noted. |

## 5. Docs accuracy

5.1 and 5.2: see 2.6 and 2.7. 5.3 (25 MP), 5.4 and 5.5 (accents), 5.6 (`Server-Timing`), 5.7 (tmpfs),
5.8 (registry password), 5.9 (local latency figures), 5.10 (two sideways reads), 5.11 (browser test
claims): **all accepted and fixed** in README, SECURITY.md, LIMITS.md, DEPLOY.md and
tests/browser/README.md.

## 6. Tests

Added: 6.2 (59a583d), 6.3, 6.4, 6.5 (backend part), 6.6 (`tests/unit/test_security.py`), 6.9.
Not added: 6.1 (the policy is documented, not something a fixture can prove about the real
recognizer), 6.5 browser assertion, 6.7, 6.8 (browser tests; deferred with 7.13), 6.10 (deferred
with 7.12).

## 7. Ship list

7.1 to 7.7 and 7.9: done as above. 7.8: resolved (2.6). 7.10 to 7.13: deferred; noted in
SECURITY.md (7.10) and here (7.11 done, 7.12, 7.13 open).
