1. **Ship approach 4. Ranking: 4 > 2 > 3 > 1.** Keep `Needs review`, with the existing `noise` classification, diff, and crop from `build_report`. It is honest, already implemented, adds no latency, and is defensible from the small 10-label evaluation. Approach 2 is the best experiment, but an English-only recognizer cannot represent `č` or `é`, so it cannot independently disprove the multilingual reading; use it as review assistance, not to set `exact=True`. Approach 3 uses correlated observations and sequence voting can manufacture a string no run produced. Approach 1 is invasive and effectively embeds the rejected normalization inside decoding. A reviewer should prefer two clearly disclosed OCR false alarms over an unsupported statutory pass.

2. In approach 1, mask `preds` either immediately after `preds = self.session(norm_img_batch)` in `TextRecognizer.__call__`, or on a copy at the start of `CTCLabelDecode.__call__`, before both `argmax(axis=2)` and `max(axis=2)`. Predictions are `[batch, timesteps, classes]`; the third axis is established by those calls.

   Preserve class `0`: `CTCLabelDecode.get_character` inserts `"blank"` at index 0 and `get_ignored_tokens` removes index 0. Dictionary characters therefore shift by one; space ends up at the final index. Build the mask by enumerating `postprocess_op.character`, not by indexing the raw dictionary. Preserve every required digit and punctuation character as well as ASCII letters.

   Risks:

   - Masking `č` does not imply `c` wins; blank or an unrelated class may be runner-up.
   - Masking blank creates junk in width-padded timesteps produced by `TextRecognizer.resize_norm_img`.
   - CTC duplicate removal in `CTCLabelDecode.decode` must run after the constrained argmax.
   - Recompute probabilities from the constrained table or confidence no longer describes the selected characters.
   - Copy `preds` so the original decode remains available.
   - Per-line top-*k* is insufficient unless it always contains the best allowed class.
   - `TextRecognizer.__call__` sorts and batches lines, so retained logits must be mapped back through `indices`.
   - The warning is identified only later by `find_warning`; the present `RapidEngine.recognize` exposes decoded strings, not logits. Warning-only dual decoding therefore requires internal-library plumbing or a second recognition pass.

3. Use one perspective-normalized crop per `WarningSpan.lines` quad, not an axis-aligned bounding box. Expand each quad roughly 3–5% at the left/right and 10% of line height above/below, clip to the image, then warp to a horizontal rectangle. Bounding boxes admit adjacent lines and preserve skew.

   The boxes returned through `_to_lines` are canonical upload coordinates, including rotation/scale reversal by `to_canonical`; crop from the corresponding canonical source image or explicitly map them back to the retained working array. `process_image` currently discards that array, so it must be retained or decoded again.

   Call the secondary engine through `RapidOCR.__call__(use_det=False, use_cls=False, use_rec=True)` and preserve the original line order. Join all returned lines with `join_hyphenated`, then apply only `_canon_form` and require a complete literal match through `compare_warning`. Do not splice English characters into the multilingual transcript. Run `anchor_caps_status` on the re-read anchor and require `Status.match`. Evidence boxes remain the original quads; retain both transcripts and model identities in the audit output. Given the English alphabet limitation, treat agreement as corroboration for the reviewer, not sufficient grounds to override a conflicting accent-capable read.

4. Document `exact` as: “The authoritative OCR transcript, produced by a recognizer capable of representing plausible printed characters, equals `CANONICAL` after only `_canon_form` whitespace and typographic-punctuation normalization.” No accent folding, confusable mapping, voting, or canonical-guided substitution may participate; those remain diagnostic operations in `classify_difference`.

   A constrained decoder or English-only verifier cannot upgrade a conflicting accent-capable transcript to exact. It may report “English-constrained read matches” or “likely OCR noise.” A human confirmation can produce a separately named and audited `human-confirmed exact` result. This preserves the distinction already enforced by `compare_warning` and `build_report`.

5. The cheapest useful addition is a recognition-only, native-resolution re-read of each disputed quad using the existing multilingual recognizer through `RapidOCR.__call__(use_det=False)`. It avoids another detector and retains the ability to distinguish accented characters. Define it beforehand as the authoritative high-resolution warning pass, rather than majority-voting outputs; ship it only after regression-testing clean and problem variants.

   Even cheaper: change no OCR and make the existing result less alarming. `classify_difference` already labels these cases `noise`, while `compare_warning` keeps `exact=False`; surface that as “likely OCR artifact—confirm against crop” with the existing evidence from `build_report`.