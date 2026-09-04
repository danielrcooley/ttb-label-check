---
id: 005
type: code-review (incremental, scoped)
status: answered (response in 005-real-labels.response.md; dispositions in 005-real-labels.dispositions.md)
requested_by: Claude (builder), at the author's request
reviewer: Codex (reviewer)
date: 2026-09-04
inputs: the diff 2b7fc94..af9e239 plus the current text of every changed source, test and doc file and the unchanged files they depend on (appended after this request)
---

# Request 005: review of the real-label changes (D-035 to D-038)

## Context
Same project as reviews 001-004. After review 004 the builder pulled 150 approved label applications
from TTB's Public COLA Registry (`tools/cola_fetch.py`), scored the tool against them
(`tools/evaluate_real.py`, results in `docs/EVAL_REAL.md`), hand-checked nine records against their
images, and changed the product in response (decision log entries D-035 to D-038):

- "exact" for the warning statement now ignores letter case and spacing, and nothing else; the
  former "case" assessment is gone; `word_diff` aligns case-insensitively (`app/pipeline/warning.py`).
- When no usable statement is found upright (none, or similarity under 0.5), each readable image is
  re-read rotated 90 and 270 degrees, then once at bounded full resolution (2048 px) if the image is
  larger than the working size; only the lines of a warning span that beats the upright read are
  kept (`app/services.py`, `_rescue_sideways_warning`; settings `warning_rescue*`).
- The "same column" filter in the span search measures overlap across the text direction, so lines
  read from a rotated image are joined (`_column_overlap`); the anchor may be split over two lines
  (`_anchor_at`); the noise classifier tolerates one slip (OSA distance 1) in words of four or more
  letters, hyphenated line breaks in capitals, and a bare number inserted from a neighbouring line.
- Reading order: within a row, lines whose left edges sit within half a line's thickness share a
  column and stay top to bottom (`app/pipeline/match.py`, `_columns_then_down`).
- Bottler comparison folds "Bottled by" style prefixes and corporate forms on both sides
  (`fold_company` in `app/pipeline/normalize.py`, `bottler_check` in `app/pipeline/compare.py`);
  the fuzzy review threshold dropped from 90 to 80.

The app is deployed on Azure Container Apps at this commit (2 vCPU, 4 GiB, 2 OCR workers; one
image costs about 2.0 s of engine time there, 1.45 s on the builder's laptop). The assignment's
emphasized requirements are: a verdict in five seconds, a screen a non-technical person can use,
batch uploads, and the warning statement checked for exact wording. Submission is in about 36 hours.

## What we need from you
Terse numbered lists, most severe first, file and line references into the attached files. No
preamble, no restating the code. Where you are not sure, say so in five words and move on.

1. **Bugs introduced by these changes.** Wrong verdict, crash, hang, held or leaked slot, wrong
   coordinates on the evidence lines that the rescue appends, wrong timing, a statement that is now
   missed or mis-joined. Pay particular attention to:
   `app/pipeline/warning.py` (`find_warning` iterating each group in both directions,
   `group.index(head[-1])`, `_column_overlap` choosing the axis per pair, `_anchor_at`'s split
   anchor, `_same_word_modulo_noise`, `classify_difference` with the new insert rule);
   `app/services.py` (`process_images` and `_rescue_sideways_warning`: the slot taken after the
   per-image slots were released, `floor` across images, `zip(strict=True)`, `p.lines.extend`,
   `BusyError` swallowed, `ocr_ms` accounting, what happens on cancellation mid-rescue);
   `app/pipeline/match.py` (`_columns_then_down`: the tolerance from the whole image's median
   thickness, chaining by the previous column's first line, rotated images);
   `app/pipeline/compare.py` (`bottler_check`: evidence remapped by box equality, `check.expected`
   overwritten after the folded comparison, the "Label says" note);
   `app/pipeline/normalize.py` (`fold_company` regex and token set, `join_hyphenated` now joining on
   any letter).
2. **False passes and false alarms.** For each rule change, can a label that is genuinely wrong now
   come back Ready for approval (a wording change that the slip tolerance or the case/spacing rule
   hides; a bottler that is a different company after folding; a brand at 80-89 that is a different
   brand)? Can a correct label now be sent to Issues? Give the concrete input for each. Check the
   case/spacing decision against the regulation text in `docs/REGULATIONS.md` (27 CFR 16.21 and
   16.22): is anything the regulation requires no longer checked, and does the "exact" note in the
   product still tell the truth?
3. **Latency against the five-second requirement.** Count the engine passes a request can cost
   after these changes, for one image and for a front-and-back pair, interactive and batch, on the
   deployed sizing above. State the cases where the interactive path now exceeds five seconds
   (a single front-label upload with no statement; a pair whose statement is genuinely missing;
   a large image) and say which of those an evaluator is likely to try. Rank the cheapest ways to
   keep the rescue's benefit inside the budget (parallel reads across slots, a time budget, running
   the rescue only for some requests, resolution only, and anything else), with the verdict each
   would change on the real-label corpus as far as you can tell from `docs/EVAL_REAL.md`.
4. **The evaluation tooling and its claims.** `tools/cola_fetch.py`: is it as polite and as
   bounded as its docstring says (delay, caps, resumability, session handling, error paths); does
   anything in it write outside `tests/fixtures/real/`; is the registry use defensible as described?
   `tools/evaluate_real.py`: are the numbers in `docs/EVAL_REAL.md` computed the way the document
   describes them (present, exact of present, match-or-review, origin found, read rates, latency
   percentiles); any double counting, denominators that drift, or a metric that flatters the tool?
   Does the hand-check section make claims the aggregate does not support?
5. **Docs accuracy.** Statements in README.md, LIMITS.md, EVAL.md, EVAL_REAL.md, REQUIREMENTS_TRACE.md
   and DECISIONS.md (D-035 to D-038) that the code as attached does not support, numbers that no
   longer match, and any place the product still describes the old behaviour (a "case" assessment,
   threshold 90, "exact means exact" without the case/spacing qualification).
6. **Tests.** Behaviors introduced by these changes that no attached test pins, ranked by the damage
   a regression would do. Name the test you would add in one line each.
7. **Ship list.** What must be fixed before submission and what can wait, each with an effort
   estimate (S: under 30 minutes, M: under 2 hours, L: more).

## Rules
Read-only; report only. Do not run commands or modify files. Treat the code as the truth and the
docs as claims to be checked against it. Cite by file and line number as they appear in the bundle.
The project rules in AGENTS.md hold (the tool recommends and never approves; heuristic findings are
Needs review, never Fail; nothing stored; no cloud API in the verification path). D-032 (ASCII
alphabet at decode) is the author's decision and is not reopened here.
