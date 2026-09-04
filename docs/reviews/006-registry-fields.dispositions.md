# Dispositions for consult 006 (verdict rules for real application data)

Each point in `006-registry-fields.response.md` was checked against the code and the tally before
anything changed. The product decisions are recorded as D-041.

| # | Recommendation | Disposition |
|---|---|---|
| 1 | Bottler: parse item 8 into name candidates (the "Used on label" name first), corporate suffixes reattached, city/state/ZIP; match names folded; city and state corroborate; name and address = Match; name only = Needs review; a different company in the label's own responsibility statement = Needs review with registry data; nothing resembling = Needs review | **Accepted.** `split_registered_party` in `normalize.py`; `bottler_check` tries the whole line and each name, keeps the best read, checks city and state on the label, and never returns a hard status: a different name on a "bottled by" line is review with both names in the note, because the applicant and the lawful bottler may differ. Pinned by `test_bottler_registered_line_against_the_label_four_ways` and `test_split_registered_party_takes_apart_colas_item_8`; the brief's short form still matches as a whole line. |
| 2 | Class/type: review-only when the wording differs; no hard mismatch is defensible without a designation table | **Accepted.** `_class_check`: Match when the text agrees, otherwise Needs review with the closest text and the reason. What is lost (automatic detection of a genuinely wrong designation) is stated in LIMITS. |
| 3 | Alcohol required but not read: Needs review; keep numeric disagreements hard | **Accepted.** Both unread branches are review with the reason; the three mismatch branches are unchanged. |
| 4 | Revised tally and honesty: no questionable row becomes Ready | **Accepted as the check to run.** Re-measured on the deployed build after the change (README, LOADTEST). Blank net contents keeps every registry row at review or worse, as the reviewer noted. |
| 5.1 | Candidate splitting existed only in the evaluator | **Accepted.** The evaluator now calls the product's `bottler_check` with the full registered line, so its applicant rows measure the product path. |
| 5.2 | Blanket hard `not_found` contradicts the heuristic rule | **Accepted for class, bottler, alcohol and origin.** Brand stays hard: the brand is the label's largest text and a brand the engine cannot find is what an agent must see first; the crop shows the closest text. Recorded in D-041. |
| 5.3 | Origin: any country anywhere matches; absence was hard | **Partially.** Absence is now review; a label origin statement ("Product of ...") naming something else is a hard mismatch with that line as evidence. The "anywhere" match is unchanged and stated in EVAL_REAL. |
| 5.4 | The evaluator shrinks over-limit images; deployment rejects them | **Noted.** Stated in EVAL_REAL's read-me-first list; the deployment's 25 MP limit is the product's documented behaviour and the batch screen names the image and the size. |
| 5.5 | Table-wine alcohol requirement bug fixed | Noted; pinned by a parametrized test. |
| 6 | Ship list | 1-3 and 6 done; 4 done for the four checks named; 5 done by re-running the live batch and the real-label evaluation after the change. |
