# Dispositions for review 003 (design consult on accented letters, Codex, 2026-09-04)

Reviewer ranking: do nothing (4) > English second opinion (2) > scale voting (3) > constrained decoder (1),
with a fifth suggestion: a recognition-only, native-resolution re-read of the warning lines with the
same accent-capable model, defined beforehand as the authoritative pass.

| Point | Disposition |
|---|---|
| Principle: a legal "exact" must not paper over instrument error; no second opinion may override an accent-capable read | **Accepted** and kept. |
| Suggestion 5: native-resolution re-read | **Tested and rejected on evidence.** On five labels the re-read fixed one case, produced a different stray accent on another ("bęverages"), and turned a previously exact label non-exact. The artifacts are random per read, so any re-read policy becomes selection bias. |
| Ranking "do nothing" first | **Overruled by the engineer**, who does not accept a system that trips on accents in the one statement that matters most. |
| Approach 1 critique (invasive; embeds normalization in decoding) | **Partially accepted.** Implemented as a documented recognizer configuration applied to every line (one transcript, literal comparison unchanged), not as a warning-only second decode. Blank preserved; probabilities and logits handled; mask built from the decoder's own character list, as the review specified. Unit-tested. |
| Approach 1 risks listed (runner-up may be blank; batching order) | **Accepted.** Blank stays allowed so a suppressed winner can decode to nothing rather than junk; the wrapper sits inside the batch decode so ordering is untouched. |
| Docs statement of when "exact" is legitimate | **Accepted.** LIMITS.md and DECISIONS.md D-032 state the alphabet restriction and its consequence for accented print. |
