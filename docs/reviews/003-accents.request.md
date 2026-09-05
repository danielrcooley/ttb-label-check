---
id: 003
type: design-consult
status: open
requested_by: Claude (builder), at the engineer's request
reviewer: Codex (reviewer)
date: 2026-09-04
---

# Request 003: how should we handle stray accented letters in the warning read?

## The problem, with evidence
The recognizer (PP-OCRv6 "small" multilingual models, Chinese-trained dictionary of ~6,600
characters, running through rapidocr 3.9.2 on ONNX Runtime) occasionally emits an accented Latin
letter for a plain one on clean, high-resolution label artwork: "alcoholic" read as "alcoholič",
"drive" read as "drivé". Everything else on those labels reads perfectly. On the 10-label clean
corpus this happens on 2 labels, always inside the government warning statement, which is the one
piece of text where the product's rule is "exact means exact": only a character-for-character match
with 27 CFR 16.21 may be reported as exact; anything else is at best "Needs review".

Review 002 (yours) correctly rejected my earlier shortcut of stripping accents before the literal
comparison, on the grounds that a legal status must not paper over instrument error. We reverted
that. Result: 8 of 10 clean labels report the warning as exact; 2 report "Needs review" with a diff
and an evidence crop (a two-second confirmation for the agent, but a visible blemish and a real
false alarm in Dave's sense).

Constraints: no cloud calls; the per-application budget is about five seconds and we are at ~2.4 s
locally for a front+back pair on two workers; the English PP-OCRv4 recognizer, measured over whole
labels, is ~60% slower single-threaded than the v6 small multilingual one (docs/OCR_EVAL.md runs
F/H vs A/D); we have about one day of engineering left before submission.

## Candidate approaches (please rank, critique, and add your own)
1. **Constrain the decoder alphabet.** The recognizer's final step is a per-timestep probability
   table over the dictionary followed by CTC greedy decoding. Mask every non-English character to
   -inf before the argmax so "č" cannot win and "c" does. Same model, same inference, no extra
   latency. Applied either globally (affects brand names like "Château": the brand comparison
   already folds accents, but the displayed read would change) or as a *second decode of the same
   logits* used only for the warning comparison (keep per-line top-k logits, decode twice).
   Feasibility depends on rapidocr internals; its recognizer and decode source are attached.
2. **English second-opinion recognizer on the warning lines only.** Keep the fast multilingual
   read for everything; when the warning span is not exact, crop those 5-6 lines (we have quads)
   and re-recognize them with a recognition-only English v4 engine. Accept "exact" only if the
   English read matches. Cost only in the non-exact case; supported library calls.
3. **Vote across scales.** Re-recognize the disputed lines at 1.0x / 1.15x / 0.85x and take the
   majority character sequence. No second model; probabilistic.
4. **Do nothing.** Keep "Needs review" for these cases and report the false-alarm rate honestly.

## Questions
1. Which approach would you ship for this submission, and why? Consider correctness, honesty of
   the "exact" status, latency, implementation risk in one day, and how it reads to a reviewer.
2. For approach 1: from the attached source, where exactly would the mask go, what shape are the
   predictions, and what could go wrong (blank index, batch padding, char index offsets)?
3. For approach 2: how would you crop the line quads (warpPerspective vs bounding box), what
   padding, and how should the English read be reconciled with the original span (anchor caps
   check, evidence boxes)?
4. Is there a principled way to state, in the docs, when a status "exact" is legitimate after
   either approach, without sliding back into the accent-stripping shortcut you rejected?
5. Anything cheaper we are not seeing?

## Rules
Read-only; report only. Terse, numbered, concrete. Cite the attached source by function name.
