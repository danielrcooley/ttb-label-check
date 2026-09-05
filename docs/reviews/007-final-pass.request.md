---
id: 007
type: code-review (incremental, pre-submission)
status: answered (response in 007-final-pass.response.md; dispositions in 007-final-pass.dispositions.md)
requested_by: Claude (builder), under the engineer's standing instruction to confer with the reviewer when it helps
reviewer: Codex (reviewer)
date: 2026-09-04
inputs: the diff af68305..HEAD (everything after review 005) plus the current text of every changed source, test and doc file and the unchanged files they depend on (appended after this request)
---

# Request 007: final pass over everything that landed after review 005

## Context
Same project as reviews 001-006. After your review 005 (real-label changes) and consult 006 (which
findings may fail an application), the builder shipped, in this order, with the engineer testing each
change by hand on 146 real applications from TTB's Public COLA Registry:

- D-040: net contents may be blank in the application (form and spreadsheet); blank = Needs review
  with the label's value shown, never Ready. The COLA form has no such field. (`app/schemas.py`,
  `app/csvio.py`, `app/pipeline/compare.py` `_net_contents_check`.)
- D-041: verdict rules against real registry data, the matrix you agreed in 006: the registered
  bottler line is taken apart (`split_registered_party` in `app/pipeline/normalize.py`), name and
  address = Match, name only = Needs review, another party or nothing = Needs review with the reason;
  class/type is review-only; an alcohol statement that is required but unread, and an unread origin,
  are review; an origin naming another country and numeric disagreements stay issues; brand and the
  warning unchanged; "Table Red/White Wine" no longer requires an alcohol statement
  (`alcohol_statement_required` in `app/pipeline/parsers.py`). Then from the first hands-on look at
  the panels: a registered name printed whole inside the label's bottler line is a Match, a class
  that is not found shows no "closest text", and barcode digits glued onto a warning word are noise
  for review (`classify_difference`, `_same_word_modulo_noise` in `app/pipeline/warning.py`).
- Batch screen: decision buttons readable in Windows contrast themes, clicks read the current
  decision; export columns `what_to_look_at`, `elapsed_ms`, `exported_at`.
- D-042: an Accessibility page with the statement and a Light / Dark / match-my-device display
  choice kept in localStorage, applied before first paint by `app/static/theme.js`; the dark palette
  is the block at the end of `app/static/app.css`.
- D-043: the single screen records a decision (Approve / Reject / Flag + note), exports one CSV row
  with the batch export's columns, or prints; shared code in `app/static/render.js`
  (`decisionControls`, `issueTexts`, `exportRow`, `csvCell`, `downloadCsv`, `exportStamp`), used by
  `app.js` and `batch.js`.
- D-044: bold type of the warning statement is measured from the pixels. `app/pipeline/typeface.py`
  (Otsu ink, distance transform, stroke = four times the mean distance, over the unpadded box height;
  a line carrying the heading is split head / tail in proportion to the characters; gates: box height
  >= 24 px and stroke >= 3.8 px). `services._to_lines` measures every line on the array the engine
  read (upright, rotated, rescue and full-resolution reads alike). `warning.type_weight_ratio`
  compares the heading with the rest of ITS OWN line, or its stroke in pixels with the other lines
  when it stands alone; `type_weight_status`: >= 1.15 Match on both format rows, <= 1.05 Needs review
  on both with one note, between = inconclusive (Not checked), unmeasured = Not checked with the
  reason; `compare._verdict` treats the bold review like the caps review. Calibration is in D-044.
- Latency: `cv2.setNumThreads(1)` in typeface.py, greyscale once per read; `tools/loadtest.py` now
  prints the server's own timing (`timing.total_ms`) next to wall time, and the README's deployed
  rows cite it.

Numbers now claimed (check them against the attached code and docs): 168 unit + 18 integration
tests; on the deployed app (2 vCPU, 4 GiB, 2 workers, server's own clock) front and back for one
user p95 2.96 s, two users p95 4.32 s, front alone with the re-read round p95 3.92 s, batch path
p95 1.92 s per image; the 146 real applications on the deployed build: 105 Needs review, 41 Issues,
0 errors, 0 Ready (blank net contents), bottler matched on 102; the 150-record evaluation: applicant
match 70 percent, warning 92 exact / 34 noise / 22 wording / 2 absent, type weight 34 measurable /
29 heavier heading / 5 inconclusive / 0 flagged / 16 too small.

Submission is within about 48 hours: the repository goes public, the URL is https://labelcheck.dev,
and there may be no interview. This is the last independent pass. The engineer's standing
instruction to both agents is to work as the best practitioner in the field would.

## What we need from you
Terse numbered lists, most severe first, file and line references into the attached files. No
preamble, no restating the code. Where you are not sure, say so in five words and move on.

1. **Bugs introduced by these changes.** Wrong verdict, crash, hang, wrong coordinates, wrong
   timing, a measurement taken on the wrong pixels. Pay particular attention to:
   `app/pipeline/typeface.py` (`stroke_ratio` on Otsu with inverted or light-on-dark print, thin
   or empty crops, the distance transform's border, `_crop` clamping, `measure_line`'s head/tail
   split by character proportion when the heading is a prefix of a longer line, box shapes for
   rotated reads);
   `app/services.py` `_to_lines` (is the array it measures the same array whose coordinates the
   boxes are in, for the upright read, the rotation retry's kept and losing reads, the rescue
   reads at 90 / 270 and at full resolution, and JPEGs decoded at reduced size under D-033; does
   the measurement run once per line or more; is weight carried through `_adopt` and the
   evidence remap);
   `app/pipeline/warning.py` (`type_weight_ratio` choosing head/tail versus stroke-in-pixels
   against other lines; which lines count as "the other lines"; `type_weight_status` thresholds
   and the two format rows; `build_report`'s wiring; `classify_difference` with the barcode rule:
   can it hide a real wording change);
   `app/pipeline/compare.py` (`bottler_check` four ways and the whole-name containment, evidence
   and `expected` after the folded comparison, `_class_check` with no closest text, `_alcohol_check`
   unread branches, `_origin_check`, `_net_contents_check` when the application is blank,
   `_verdict` with the bold review);
   `app/pipeline/normalize.py` (`split_registered_party`, `_state_code`, `RegisteredParty.state_forms`,
   `company_forms`);
   `app/csvio.py` and `app/schemas.py` (blank net contents; the batch screen's "no usable rows"
   message);
   the frontend (`app.js` `renderDecision` / `exportSingle` snapshot at check time and reset on a
   new check; `batch.js` `decisionCell` / `exportCsv`; `render.js` `exportRow` when a result is
   missing or errored; `theme.js` before first paint under the CSP in `app/security.py`).
2. **False passes and false alarms.** For each rule change give the concrete input. Can a label
   that is genuinely wrong now come back Ready (a different company whose name contains the
   registered name; a class that is wrong but "found"; an alcohol statement that is absent on a
   product that needs one; a warning with a real wording change hidden by the barcode-noise rule;
   an all-bold statement that measures above 1.15 through a split artifact)? Can a correct label
   now be sent to Issues or to Needs review it does not deserve (a heading measured against a
   light body font; a bottler whose city is printed with the state spelled out; a blank net
   contents on a form that never had one)? Is AGENTS.md rule 4 (heuristic findings are never
   failures) honoured in every new branch, and is rule 3 (the tool never approves) honoured by
   the new decision controls and export?
3. **Latency against the five-second requirement.** Cost of the weight measurement per line and per
   read, where it runs on the interactive path and on the batch path, the greyscale-once change,
   the OpenCV thread pin; anything that now runs per line that need not; the worst interactive
   case on the deployed sizing after these changes, and whether the README's deployed rows state
   the measurement honestly (server clock, wall caveat).
4. **Accessibility of the new UI.** The dark palette in `app.css`: name every text/background pair
   you can compute from the attached values that is likely under WCAG 2.1 AA (4.5:1 text, 3:1 UI
   and focus); forced-colors behaviour of the decision buttons, the theme radios and the tiles;
   keyboard reach and focus order of the new controls; what a screen reader announces when a
   decision is recorded and when the theme changes; the print stylesheet; whether the Accessibility
   page's statements (keyboard alone, 200 percent zoom, phone, contrast themes, announcements,
   local storage only) are true of the attached code.
5. **Security and privacy.** The CSV export (`csvCell`'s formula guard, quoting, the BOM, the note
   free text), the decision note's rendering path, the print path, localStorage contents, any new
   request parameter or header, anything now logged or stored, the CSP after `theme.js`.
6. **Docs accuracy.** Statements in README.md, LIMITS.md, EVAL.md, EVAL_REAL.md, REGULATIONS.md,
   REQUIREMENTS_TRACE.md, LOADTEST.md, SECURITY.md and DECISIONS.md (D-040 to D-044) that the code
   as attached does not support; numbers that no longer match; any place that still describes the
   old behaviour (net contents required, class mismatch as an issue, bold "not checked", the old
   export column names, the accessibility statement living on About).
7. **Tests.** Behaviors introduced by these changes that no attached test pins, ranked by the damage
   a regression would do. Name the test you would add in one line each.
8. **Submission readiness and ship list.** The repository is about to be evaluated, without an
   interview, by a federal AI engineering group that knows the code was written by directing
   Claude Code with Codex reviewing. (a) What in the attached material would make a senior reviewer
   there mark it down: inconsistencies between documents, overclaiming, a number that cannot be
   reproduced from the repo, prose that reads as generated filler, a decision entry that does not
   say what was actually decided. (b) Anything that should not be public (paths, names, identifiers,
   data that is not ours to redistribute). (c) The ship list: what must be fixed before submission
   and what can wait, each with an effort estimate (S: under 30 minutes, M: under 2 hours, L: more).

## Rules
Read-only; report only. Do not run commands or modify files. Treat the code as the truth and the
docs as claims to be checked against it. Cite by file and line number as they appear in the bundle.
The project rules in AGENTS.md hold (the tool recommends and never approves; heuristic findings are
Needs review, never Fail; nothing stored; no cloud API in the verification path). D-032 (ASCII
alphabet at decode) and the verdict matrix of D-041 (agreed in consult 006) are the engineer's
decisions: check the implementation, do not reopen the policy.
