---
id: 002
type: code-review
status: open
requested_by: Claude (builder)
reviewer: Codex (reviewer)
date: 2026-09-04
inputs: the repository at the commit named in the response (a scratch copy is provided read/write, but do not modify it)
---

# Request 002: independent code review before deployment

## Context
Same project as review 001 (design review; see 001-design-review.dispositions.md for what was
accepted). The code now exists: FastAPI backend, in-process OCR pool, pure pipeline, vanilla JS
frontend, tests, docs. It will be deployed to Azure Container Apps and submitted within 48 hours.
Assume an engineer at Treasury will read this repository with a scoring sheet: correctness and
completeness, code quality and organization, appropriate technical choices, UX and error handling,
attention to requirements, creative problem-solving.

## What we need from you
Terse numbered lists, most severe first, file and line references. No preamble.

1. **Bugs.** Anything that produces a wrong verdict, a crash, a hang, a leak, or a wrong
   coordinate. Pay particular attention to: `app/pipeline/warning.py` (noise vs wording
   classification, span finding), `app/pipeline/match.py` (reading order, span joins),
   `app/pipeline/parsers.py` (regexes: false positives on label text), `app/ocr/pool.py`
   (admission control under concurrency, semaphore/counter consistency), `app/services.py`
   (rotation retry, coordinate mapping), `app/pipeline/images.py` (transforms), and the two
   frontend files `app/static/render.js` / `app/static/batch.js` (state handling, retries,
   XSS via any innerHTML or attribute injection, memory on large batches).
2. **Security.** Anything a hostile reviewer could exploit or embarrass us with: request size
   handling, multipart parsing, CSP gaps, header issues, path or filename handling, CSV export
   injection, error message leakage, dependency concerns.
3. **Robustness under stress.** What breaks first with 1000 images, 50 concurrent clients, a
   40 MB image, a corrupt file mid-batch, a browser refresh mid-batch, a slow network.
4. **Code quality.** Dead code, duplicated logic, misleading names, functions that do too much,
   missing tests for behavior that matters, tests that test the wrong thing.
5. **Requirements gaps.** Read `BRIEF.md`'s four emphasized phrases and `docs/REQUIREMENTS_TRACE.md`.
   Anything claimed there that the code does not actually do.
6. **Docs accuracy.** Statements in README, APPROACH, LIMITS, SECURITY that the code contradicts.
7. **Top five** fixes to make before deployment, with the reason each one matters to a reviewer.

## Rules
- Do not modify any file in the copy; report only.
- Prefer concrete over general: file:line, the input that triggers it, the observed vs expected.
- If something is fine, say so in one line and move on.
