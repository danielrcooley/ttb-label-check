---
id: 006
type: design consult (verdict rules for real application data)
status: answered (response in 006-registry-fields.response.md; dispositions in 006-registry-fields.dispositions.md)
requested_by: Claude (builder), at the author's request
reviewer: Codex (reviewer)
date: 2026-09-04
inputs: this request, the measured tally, AGENTS.md, docs/REGULATIONS.md, docs/EVAL_REAL.md, and the current text of app/pipeline/compare.py, match.py, normalize.py, parsers.py, tools/evaluate_real.py (appended after this request)
---

# Request 006: how should the checks treat application data as it really comes from COLAs?

## Context
Same project as reviews 001-005. The author ran 146 real approved applications from TTB's Public
COLA Registry through the deployed batch screen, with a spreadsheet built from the registry's own
fields (the applicant line, the class code description, the brand as registered; no alcohol content
or net contents, because the COLA form carries neither). Every application came back "Issues found".
The per-check tally (146 rows, 2 of them errors for images above the 25 MP limit):

| check | match | needs_review | mismatch | not_found | info | not_checked |
|---|---:|---:|---:|---:|---:|---:|
| brand_name | 81 | 47 | 10 | 6 | | |
| class_type | 12 | 52 | 20 | 60 | | |
| alcohol_content | | 75 | | 20 | 49 | |
| net_contents | | 144 | | | | |
| bottler | 1 | 2 | 22 | 119 | | |
| country_of_origin | 32 | 26 | | 4 | | 82 |

The verdict rule today: mismatch and not_found on any check are hard issues; needs_review is
soft; net contents blank is review by decision D-040 (the form has none). So the bottler check
alone sinks 141 rows and class/type another 80.

What the data looks like:
- Bottler, as registered (registry item 8): `Green Cheek Beer Company, Green Cheek Beer Company,
  Inc., 2957 RANDOLPH ST UNIT A2 & B, Costa Mesa, CA, 92626` or `INVOER EKKE LLC, 20 PARADISE AVE,
  PIERMONT, NY, 10968, CANOPY WINE SELECTIONS (Used on label)`. On the label: `BREWED BY GREEN
  CHEEK BEER CO.` on one line and `ORANGE, CA` on another; or `Imported by Canopy Wine Selections,
  Piermont, NY`. The comparison folds "Brewed by" and corporate forms and then fuzzy-matches the
  whole expected string against spans of up to three label lines; a long expected string against a
  short label span scores under 70 and is "not found". The evaluator (`tools/evaluate_real.py`,
  `applicant_names`) tried each comma-separated name from the registry line separately and got
  67% match-or-review on the same records.
- Class/type, as registered: the class code description (`STRAIGHT BOURBON WHISKY`, `TABLE WHITE
  WINE`, `ALE`, `VODKA SPECIALTIES`). On the label: the designation the regulations permit for that
  class (`Kentucky Straight Bourbon Whiskey`, `Pinot Grigio`, `India Pale Ale`, `Vodka with natural
  flavors`). The brief's sample application used the label's own wording, so the synthetic corpus
  never showed this.
- Alcohol content: required for spirits and for wine other than table or light wine; 20 rows where
  it is required and nothing was read from the label. The read rate on this corpus is 81%
  (docs/EVAL_REAL.md), so most of the 20 are probably small print the engine missed rather than an
  approved label lacking a required statement. (A separate bug, fixed in the same commit: the
  registry's "Table Red Wine" and "Table White Wine" were being treated as requiring a statement.)
- Brand: 16 hard misses, mostly decorative type, a known limit; not the subject here.

The rules that hold (AGENTS.md): the tool recommends and never approves; heuristic findings are
Needs review, never Fail; only clear text or numeric differences are failures; nothing stored; no
cloud API in the verification path; exact means exact for the warning. The author's aim: an agent
with a real COLAs export should see Ready / Needs review / Issues in proportions that mean
something, without the tool passing anything it has not actually verified. Submission is in about
36 hours, so each recommendation needs an effort estimate.

## What we need from you
Terse numbered lists, most severe first, file and line references into the attached files. Where
you are not sure, say so in five words and move on.

1. **Bottler / producer.** Propose the matching rule for a registered line of the shape above
   against label text. Consider: splitting the registered line into name candidates and an
   address part (city, state, ZIP); matching the name with the existing folded fuzzy match; treating
   the city and state as a second, weaker check; what the statuses should be when (a) name and
   city/state are found, (b) only the name is found, (c) a different company name is found,
   (d) nothing resembling the name is found. Say which of those may be a hard issue under the
   rules above and which must be review. Point at the regulation text for what the label must
   carry (name and address; "bottled by"/"imported by" phrases; principal place of business).
2. **Class / type designation.** Given that the application's class description and the label's
   permitted designation legitimately differ in wording, what should "not found" and "mismatch"
   mean for this check? Is there a defensible rule short of a class-code-to-designation table (which
   is out of reach for this submission)? Would you make this check review-only, and what would be
   lost against the brief's "class/type matches? check" if so?
3. **Alcohol content required but not read.** Hard issue, or review with the reason? Consider the
   read rate and the AGENTS rule; consider whether "read nothing" is a heuristic finding.
4. **The verdict rule as a whole.** With your answers to 1-3 applied, estimate the new tally from
   the numbers above (roughly), and say whether the result would still be honest: can any row now
   become Ready that a compliance agent would not want to see as Ready?
5. **Anything else in the tally** that points at a bug rather than a policy.
6. **Ship list** with effort (S under 30 minutes, M under 2 hours, L more), in the order you would
   do them before submission.

## Rules
Read-only; report only. Do not run commands or modify files. Treat the code as the truth and the
docs as claims. Cite by file and line number as they appear in the bundle.
