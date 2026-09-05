---
id: 009
type: code-review (whole repository, pre-submission)
status: answered (response in 009-final-review.response.md; dispositions in 009-final-review.dispositions.md)
requested_by: Claude (builder), at the engineer's request ("do a final review of our entire project, look for bugs, mistakes, and review the instructions again")
reviewer: Codex (reviewer)
date: 2026-09-04
inputs: the complete text of every source, test, tool, configuration and documentation file at commit 33ee00a (appended after this request as one bundle with `===== FILE: path =====` headers), plus BRIEF.md (the assignment, verbatim). Excluded for size: the OCR model files, the vendored U.S. Web Design System, the PNG fixtures and samples, docs/img, docs/regs, docs/eval.json and the earlier review transcripts (their request, response and dispositions files are included).
---

# Request 009: final review of the whole repository against the assignment

## Context
Same project as reviews 001-008. The repository is about to be tagged and submitted, with the deployed
application at the URL the README names. There may be no interview: the repository and the URL are the
whole evaluation, read by a review team that grades against the assignment in BRIEF.md. Reviews 001-008
each covered a slice; this is the only pass over everything at once, at the commit that will be
submitted, save for the documentation edits listed below.

Two edits to the README are decided and not yet made; review the repository as if they were done:
- The "Observed usability test: _USABILITY_RESULT_" clause in the "my mother could figure out" row is
  removed. No usability observation is claimed anywhere.
- The "From the author" section (`_AUTHOR_SECTION_`) is replaced by a section that states the
  prototype's specifications in relation to the assignment's guidelines and lists the engineer's
  judgment calls, in the third person ("the engineer"). The decision log keeps the same voice.

## What we need from you
Answer these nine sections in order, terse numbered lists, most severe first, with `file:line`
references as they appear in the bundle. Say "none found" when a section is empty; do not pad.

1. **Bugs.** Anything in `app/` (Python and the static JavaScript) that can crash, hang, leak a
   worker slot, return a wrong verdict, wrong coordinates, a wrong status, or a wrong number in the
   report, on inputs a reviewer could plausibly send: the three samples, the demo batch, their own
   images, odd file types, empty fields, huge or tiny images, a spreadsheet with surprising columns,
   two tabs at once, a slow connection. Include the JavaScript's handling of every error path the
   API can return (400, 413, 415, 422, 429, 503, network failure, a JSON body the client did not
   expect).

2. **The assignment, item by item.** For every requirement, request and hint in BRIEF.md, say whether
   the repository meets it, where the evidence is, and what is missing or overstated. Cover at least:
   results in about five seconds; "my mother could figure out"; batch uploads of 200 to 300; the
   warning statement exact word for word with GOVERNMENT WARNING in capitals and bold; Dave's
   judgment case ("STONE'S THROW" against "Stone's Throw"); Jenny's imperfect images (angles,
   lighting, glare); Marcus's firewall (no cloud APIs in the path), "don't do anything crazy" and
   "not storing anything sensitive"; the field list (brand, class/type, alcohol content, net
   contents, name and address of bottler, country of origin for imports, the warning); the sample
   label fields; the two deliverables (repository with setup and run instructions, approach, tools,
   assumptions; a deployed working prototype); every evaluation criterion; "document any trade-offs
   or limitations"; and "how you fill in gaps independently". Name any item the repository answers
   only with a claim and no test, measurement or documented evidence.

3. **Setup and run instructions, cold.** Follow README.md as a reviewer with a fresh machine would:
   Docker path and local Python path, then the tests. Every command, file, environment variable and
   port must exist in the bundle as the README says. List anything that would fail or confuse, and
   anything the README should say and does not (Python version, model download, how long the first
   start takes, where the samples are).

4. **Documentation accuracy.** Every number and claim in README.md, docs/APPROACH.md, docs/LIMITS.md,
   docs/REQUIREMENTS_TRACE.md, docs/REGULATIONS.md, docs/SECURITY.md, docs/EVAL.md, docs/EVAL_REAL.md
   and docs/LOADTEST.md checked against the code, the tests and each other. Stale text is the main
   risk: the "remainder of the statement not in bold" row was removed (D-046), the bold row can no
   longer read "Not checked" (D-047), the result text says GOVERNMENT WARNING rather than "the
   heading", the batch spreadsheet step is not labelled optional, the Wine tile comes first. Find any
   sentence, table row, test name, comment, screenshot caption, sample description or export column
   that still describes the earlier behaviour, and any place two documents disagree with each other.

5. **User experience and error handling.** What a first-time user of either screen meets that would
   confuse them or leave them stuck, including on a phone, at 200 percent zoom, with a keyboard only,
   with a screen reader and in a Windows contrast theme. Judge the wording of every status, verdict,
   reason and error message a user can see, in `app/static/*.js`, `index.html` and the API's error
   details.

6. **Security and privacy.** Against Marcus's "don't do anything crazy": anything stored, logged,
   sent out, or exposed that should not be; the CSV export's formula guard; upload validation;
   the Content-Security-Policy and the other headers; the container; the rate limits and their
   bypasses; secrets or personal data anywhere in the bundle (paths, names, addresses, keys, hosts).

7. **Code quality and organisation.** What a reviewer grading "code quality and organization" and
   "appropriate technical choices for the scope" would mark down: dead code, leftover debugging,
   duplicated logic, functions doing too much, inconsistent naming, comments that no longer match
   the code, tests that test nothing, dependencies that are not used, files that do not belong in
   the repository, and anything in the tools directory that a reviewer could run and get a different
   number from the one the README cites.

8. **Tests.** Behaviours a reviewer would expect to be pinned that no test in the bundle pins, ranked
   by the damage a silent regression would do; and any test that would pass with the behaviour
   broken.

9. **Ship list.** Two ordered lists: what must change before the tag, and what should be left alone
   because changing it now risks more than it gains. Then one paragraph: the single strongest and
   the single weakest thing about this submission as a reviewer would see it.

## Rules
Read-only; report only. Do not run commands or modify files. Treat the code as the truth and the
docs as claims to be checked against it. Cite by file and line number as they appear in the bundle.
The project rules in AGENTS.md hold (the tool recommends and never approves; heuristic findings are
Needs review, never Fail; nothing stored; no cloud API in the verification path; exact means exact
for the warning). Settled decisions are not reopened: D-032 (ASCII alphabet at decode), the verdict
matrix of D-041, D-046 (the two format checks are the ones the brief names) and D-047 (the bold row
is Match or Needs review). Check their implementation, not the policy.
