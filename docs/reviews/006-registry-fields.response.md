1. **Bottler / producer**

   - Parse item 8 into: named candidates before the postal address, corporate suffixes reattached; any candidate marked “Used on label”; and city/state/ZIP. Compare every name candidate using the existing responsibility-prefix and corporate-form folding, within a coherent label block; use nearby city+state only as corroboration (`app/pipeline/normalize.py:120-160`, `tools/evaluate_real.py:83-104`).
   - (a) Name plus nearby city/state: **Match**. A conflicting corporate form remains **Needs review** (`app/pipeline/compare.py:113-120`).
   - (b) Name only: **Needs review** — identity is plausible, address was not verified.
   - (c) Clearly different company in an explicit “bottled/imported/brewed by/for” statement: **Mismatch only when the expected field is the actual responsible party**. With registry applicant data, use **Needs review**, because applicant and lawful bottler may differ (`docs/EVAL_REAL.md:11-12`).
   - (d) No resembling name: **Needs review**, not a hard issue; OCR non-detection is heuristic (`AGENTS.md:20-22`, `app/pipeline/match.py:137-153`).
   - The bundle supports mandatory name/address and cites §§5.66/4.35/7.66, while expressly saying phrasing validation is out of scope (`docs/REGULATIONS.md:56-63`, `app/pipeline/compare.py:101-109`). Underlying section text not attached.

2. **Class / type designation**

   - Keep **Match** for exact/fold-equivalent text and **Needs review** for close text. Convert generic `mismatch` and `not_found` outcomes to **Needs review: registry class description is not necessarily the permitted label designation** (`docs/EVAL_REAL.md:9-12,63`; `app/pipeline/compare.py:56-71,341-345`).
   - No hard mismatch is defensible without semantic designation extraction or a class-code mapping: the current matcher merely scores the expected phrase against arbitrary one-to-three-line spans (`app/pipeline/match.py:92-134`).
   - Yes, make it review-only for this input source. What is lost: automatic detection of a genuinely wrong designation. The brief’s “matches?” check becomes triage/manual confirmation, consistent with the documented limit that designation validity is not checked (`docs/REGULATIONS.md:58-63`).

3. **Alcohol content required but not read**

   - **Needs review**, with: “A statement is required, but none could be read; inspect the label image.” Reading nothing is an OCR/heuristic result, not a clear textual difference (`AGENTS.md:20-22`).
   - The 81% read rate materially supports that treatment (`docs/EVAL_REAL.md:32-33`). Current `not_found` branches incorrectly make this hard (`app/pipeline/compare.py:158-177,302-323`).
   - Preserve hard **Mismatch** when two clearly read numeric values disagree (`app/pipeline/compare.py:178-214`). The requirement logic itself is documented and now handles colored table-wine descriptions (`app/pipeline/parsers.py:57-58,251-265`).

4. **Revised tally / honesty**

   - Of 144 completed rows: class becomes about **12 Match / 132 Needs review / 0 hard**; alcohol **49 Info / 95 Needs review / 0 hard**; bottler **at most ~48 Match / at least ~96 Needs review / 0 hard**, using the evaluator’s 33% name-match rate as an upper bound because city/state would also be required (`docs/EVAL_REAL.md:23-26`).
   - From the displayed checks alone: approximately **16–20 Issues**, **124–128 Needs review**, **0 Ready**, plus **2 image errors**. The remaining hard rows are the 16 brand misses and four origin misses, with unknown overlap.
   - Current warning behavior could raise Issues further; the evaluation has 25 absent/wording cases out of 150 (`docs/EVAL_REAL.md:40-47`, `app/pipeline/compare.py:313-318`). Warning overlap is not supplied.
   - No questionable row becomes Ready: all 144 completed rows already have blank-net-contents review, and any review blocks Ready (`app/pipeline/compare.py:224-241,324-337`).

5. **Other likely bugs**

   - Production compares the entire applicant/address string; candidate splitting exists only in the evaluator (`app/pipeline/compare.py:101-123`, `tools/evaluate_real.py:83-104`).
   - Blanket treatment of every `not_found` as hard contradicts the heuristic rule; low fuzzy similarity is explicitly what creates `not_found` (`AGENTS.md:20-22`, `app/pipeline/match.py:137-153`, `app/pipeline/compare.py:302-312`).
   - Origin can match a country appearing anywhere, not necessarily in an origin statement, while absence becomes hard. The evaluation itself calls that a proxy (`docs/EVAL_REAL.md:15`; `app/pipeline/compare.py:89-98`).
   - Real-evaluation comparability is skewed because its helper silently shrinks over-limit images whereas deployment rejects them (`tools/evaluate_real.py:57-74`).
   - The table-red/table-white alcohol bug appears fixed in the supplied code (`app/pipeline/parsers.py:57-58,257-262`).

6. **Ship list**

   1. **M:** Implement scoped bottler parsing, candidate selection, proximate city/state corroboration, and the four-status matrix; add focused tests (`app/pipeline/compare.py:101-123`).
   2. **S:** Make class/type non-equivalence and absence review-only for registry descriptions (`app/pipeline/compare.py:341-345`).
   3. **S:** Downgrade unread required alcohol statements to review; retain clear numeric mismatches (`app/pipeline/compare.py:158-214`).
   4. **M:** Replace blanket hard `not_found` handling with check-specific severity; at minimum soften origin absence (`app/pipeline/compare.py:302-323`).
   5. **M:** Re-run the deployed comparison path and report verdict counts, rather than relying on evaluator proxies (`tools/evaluate_real.py:77-104,134-158`).
   6. **S:** Record the input semantics and revised decisions in regulations/limits/decision documentation (`docs/REGULATIONS.md:56-63`, `docs/EVAL_REAL.md:7-17`).