# Approach, tools, assumptions

Two pages, as the brief asked. Depth lives in the linked documents.

## What was built and why

A compliance agent uploads the label images for one application, enters what the application
says, and gets a checklist in a few seconds: brand, class/type, alcohol content, net contents,
bottler, country of origin, and the government warning checked word for word. Every finding is
tied to the exact pixels it came from, so the agent looks at the evidence instead of hunting on
the label. A batch screen does the same for a folder of images and a spreadsheet of applications,
streaming results, recording decisions, and exporting them. **The tool recommends; the agent
decides.** Nothing is stored.

The brief's interviews carried the real requirements, and the authors bolded four of them: about
five seconds, usable by anyone, batch uploads, and an exact warning. The architecture follows
from those four plus Marcus's firewall.

- **Five seconds** ruled out a cloud vision API on a government network with blocked egress and
  also, honestly, ruled it out on latency. OCR runs in-process on a small neural text detector and
  recognizer (PP-OCR via ONNX Runtime), chosen by measurement over Tesseract and over larger
  models (`docs/BAKEOFF.md`, `docs/OCR_EVAL.md`). The two images of an application are read in
  parallel. Timing is printed on every result.
- **Usable by anyone** meant one screen, two numbered steps, one button, three one-click samples,
  and the U.S. Web Design System, which is what federal agents already see every day and is built
  for Section 508. Statuses are always an icon, a word and a color.
- **Batch** meant the browser orchestrates: it reads each image once (with the orientation retry when a
  first read is poor, never the single screen's rescue round), pairs images to applications
  by an explicit rule (a CSV column or a filename prefix; leftovers are assigned by hand, never
  guessed), compares each application as soon as its images are read, and streams rows in. The
  bulk compare endpoint serves scripted clients. The server stays stateless, which is also why it
  scales by adding replicas and why a refresh clears the session (the page says so).
- **Exact warning** meant a character-level comparison with the regulation text pulled from the
  eCFR API, where only an exact match passes. The interesting engineering is separating OCR noise
  (a dropped colon, a `0` read as `O`) from a wording change (`can` for `may`). Noise is "Needs
  review" with a diff; a wording change is a mismatch.

Two decisions the engineer would defend first. Automatic approval was never on the table, because Dave is
right that judgment is the job and because federal AI guidance requires human oversight for
decisions like this. And no LLM sits in the verification path: the firewall forbids it, the
five-second budget punishes it, and a compliance tool should give the same answer for the same
label every time, with every finding traceable to pixels. The engine sits behind a small
interface (`app/ocr/base.py`); a second-opinion provider would implement it and be pointed at an
approved endpoint inside the agency boundary. None is wired in.

## How it works

`images.py` sniffs the file type by signature, guards against oversized images, applies EXIF
orientation, downscales for OCR and keeps the transform so every box can be mapped back to the
original image. `ocr/` holds the engine and a worker pool with one engine per thread; admission
control gives interactive requests priority and refuses batch traffic with a 429 and Retry-After
rather than queueing it. `pipeline/` is pure functions with no I/O: normalization, parsers for
alcohol and net contents (the same parser runs on the application value and the label text, so
"45% Alc./Vol. (90 Proof)" compares as numbers), fuzzy matching with three outcomes, the warning
comparator, standards of fill, and the verdict. `services.py` orchestrates; `routes/` is thin.
The frontend is vanilla JavaScript modules with no build step, so a reviewer can read all of it.

## Tools used

- Python 3.12, FastAPI, Pydantic, NumPy, Pillow, RapidFuzz; RapidOCR with PP-OCR models on ONNX
  Runtime (vendored, hash-pinned, no downloads); U.S. Web Design System 3.14 (vendored).
- pytest, ruff, mypy in strict mode; Playwright for headless browser checks; Docker; Azure
  Container Apps.
- **AI coding agents, openly:** Claude Code as the builder and Codex as an independent reviewer,
  directed by the engineer. The requirements analysis, the architecture, the review passes, and every
  decision in `docs/DECISIONS.md` are the engineer's; where the builder's first proposal was wrong, the log
  says so and says who caught it. The design review and its dispositions are in `docs/reviews/`.
  Commits carry the agent trailer.

## Assumptions (gaps filled without asking)

1. The primary input is label artwork as submitted to COLA; photographs are a secondary case.
2. An application has one or more label images (front, back, neck); the warning is usually on
   the back, so images are merged before any check.
3. Application values are entered as written, including formatting like "(90 Proof)".
4. Case-only and accent-only differences between application and label are not defects.
5. Bottler and origin are checked when the application supplies them; origin is required when the
   application is marked imported.
6. Wine may omit a numeric alcohol statement when designated table or light wine; malt beverages
   may omit it under federal rules; both are reported, not flagged.
7. The five-second expectation applies to one application through the interface, not to a batch.
8. "Deployed URL we can access" means a public prototype without sign-in; the production path is
   described, not faked.
9. Reviewers may test from a managed government browser, so the page uses no CDN, no WebSockets,
   and nothing newer than widely supported web platform features.

## Trade-offs and limitations

Physical type size is outside the report (it needs a known scale, which an image does not carry);
bold type is measured from the pixels: a clearly heavier heading is a match, and anything less asks for a
look with the reason. Photographs are best effort. Class/type validity, age statements and laboratory
tolerances are out of scope. Fuzzy pairing of unlabeled images is deliberately absent. The full
list, with the enforced limits and the measured numbers, is in `docs/LIMITS.md`; the regulatory
basis of every check is in `docs/REGULATIONS.md`; security and data handling in `docs/SECURITY.md`.

## Path to production

Behind the agency identity provider (Entra ID with PIV); Azure Government; an audit record of
decisions with a retention policy; model versions promoted only after the evaluation in
`docs/EVAL.md` passes; horizontal scaling by replicas; COLA integration through the same JSON API.
