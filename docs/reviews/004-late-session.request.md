---
id: 004
type: code-review (incremental)
status: answered (response in 004-late-session.response.md; dispositions in 004-late-session.dispositions.md)
requested_by: Claude (builder), at the author's request
reviewer: Codex (reviewer)
date: 2026-09-04
inputs: the diff 79e9e04..009a407 plus the current text of every changed source, test and doc file (appended after this request)
---

# Request 004: review of everything that landed after review 002

## Context
Same project as reviews 001-003. After your code review (002) the builder implemented the accepted
dispositions (commit b473b22), fixed the container build (6da02c5), added CI publishing to Azure
Container Registry (dcbabf7, 009a407), and shipped the accent decision (ad01e40: recognizer alphabet
restricted to printable ASCII at CTC decode, D-032, overruling your "do nothing" ranking in 003).
The app is now deployed on Azure Container Apps (2 vCPU, 4 GiB, 2 OCR workers, ingress in front,
`TTB_TRUST_PROXY=true`). Submission is in about 48 hours; there may be no interview, so the repo and
the URL are the whole evaluation.

These changes were made at the end of a long session, when the builder's working context was nearly
full. The author wants an independent pass over exactly this material. The attached bundle holds:
(a) the review-002 dispositions you are checking against, (b) the full diff since 79e9e04, (c) the
current text of every file that diff touches, and (d) the unchanged files those changes depend on
(schemas, parsers, match, normalize, extract, csvio, base engine).

## What we need from you
Terse numbered lists, most severe first, file and line references into the attached files. No
preamble, no restating the code. Where you are not sure, say so in five words and move on.

1. **Bugs introduced by these changes.** Wrong verdict, crash, hang, leaked slot or counter,
   wrong coordinate, wrong size reported to the client, cancellation path that skips a release.
   Pay particular attention to: `app/ocr/pool.py` (`slot()`, `_admit()`, the cancelled-while-running
   path and the `add_done_callback` release), `app/security.py` (`AdmissionLimiter` and the
   middleware's acquire/release on every exit path, X-Forwarded-For choice behind Azure ingress),
   `app/pipeline/compare.py` (`_alcohol_check` with several candidate statements across images,
   the proof-vs-percent rule, the 0.5% not-required path, `_verdict` with `not_checked`),
   `app/pipeline/images.py` (the JPEG `draft` call and everything downstream that depends on
   `width`, `height`, `scale`), `app/pipeline/warning.py` (`_x_overlap` column filter inside the
   span search, `_anchor_score`), `app/ocr/alphabet.py` and its use in `app/ocr/rapid.py`,
   `app/services.py` (slot held across the rotation retry), `app/static/batch.js` (folder-aware
   keys, rebuild-on-input-change, backoff without a slot, cached detail panels),
   `app/static/render.js` (the size-agreement guard before cropping).
2. **Fidelity to the review-002 dispositions.** For each disposition marked Accepted or Partially,
   does the code do what the disposition says? List only the ones that do not, or that do
   something narrower or broader than stated.
3. **The alphabet restriction (D-032).** Risks in the implementation as written: blank index,
   batch shape, probabilities vs logits, the confidence values that the rest of the pipeline now
   receives (they come from the masked distribution), the rapidocr attribute names being relied on,
   what happens if the library changes shape. Is the docs' statement of the consequence honest and
   complete (LIMITS.md, DECISIONS.md D-032, EVAL.md)?
4. **CI, Dockerfile, requirements, deployment.** Anything that would break the container, the
   publish step, or the deployed app under the settings above; anything about how the registry
   credentials are handled; the `--no-deps` install and the pinned dependency list.
5. **Docs accuracy.** Statements in README.md, LIMITS.md, EVAL.md, DEPLOY.md, SECURITY.md that the
   code as attached does not support, or numbers that no longer match.
6. **Tests.** Behaviors introduced by these changes that no attached test pins, ranked by the
   damage a regression would do. Name the test you would add in one line each.
7. **Ship list.** What must be fixed before submission and what can wait, each with an effort
   estimate (S: under 30 minutes, M: under 2 hours, L: more).

## Rules
Read-only; report only. Do not run commands or modify files. Treat the code as the truth and the
docs as claims to be checked against it. Cite by file and line number as they appear in the bundle.
