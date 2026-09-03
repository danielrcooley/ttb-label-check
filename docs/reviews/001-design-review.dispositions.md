# Dispositions for review 001 (design review by Codex, 2026-09-03)

Reviewer: Codex (gpt-5.6, high reasoning), read-only, documents supplied inline.
Builder: Claude Code. Human decision-maker: Daniel R. Cooley.
Legend: **Accepted** (will do), **Partially** (do a narrower version, reason given),
**Rejected** (reason given), **Deferred** (backlog after core is green).

## 1. Missed requirements
| # | Finding | Disposition |
|---|---|---|
| 1.1 | 5-second rule needs a deployed, end-to-end, per-application p95 gate | **Accepted.** Gate is: front+back application through the API on the deployed host, p95 under 5 s, measured under concurrent batch load. Images of one application fan out to workers in parallel. |
| 1.2 | "my mother could figure out" needs an observed usability test, not features | **Accepted.** Daniel runs one observed, unprompted test with an older non-technical participant on Day 5: task, completion time, errors, verbatim confusion. Result goes in the README. Also: fewer controls on the first screen. |
| 1.3 | Batch: keep streaming, per-file failures, cancel, export; fuzzy pairing not required | **Accepted.** See 2.2. |
| 1.4 | Warning must be exact; OCR-tolerant similarity is too permissive | **Accepted.** Exact comparator preserving colon, (1), (2), commas, periods, "Surgeon General" capitalization. Exact match is the only Pass. Near-match is Needs review with a character diff, never Pass. Mismatch below a threshold. The generic normalizer is not used for this check. |
| 1.5 | Golden warning tests must be explicit in the DoD | **Accepted.** Exact pass; title-case anchor; missing comma; missing clause (2); anchor not bold; all-bold; one-word substitution. |
| 1.6 | Bottler name/address and import origin reduced to optional; should be compared when supplied, origin conditional on import | **Accepted.** Both are compared when the application supplies them and reported Not found if absent from the label. Origin becomes required when the application marks the product imported. |
| 1.7 | README must let a clean reviewer run the app alone | **Accepted.** Tested on a clean machine or clean container before submission. |
| 1.8 | Sections 10-13 violate "working core over ambitious" | **Accepted in substance.** See section 3 below and the revised DoD in ARCHITECTURE.md section 15. |

## 2. Wrong calls
| # | Finding | Disposition |
|---|---|---|
| 2.1 | One host, not two | **Accepted.** Primary Azure Container Apps. Fly kept as an emergency fallback plan, not a parallel deployment. Local Docker command tested as the last resort. |
| 2.2 | Fuzzy many-to-one pairing as default is unsafe (back labels lack signals) | **Accepted.** Default pairing is the explicit `images` column or filename convention. Fuzzy pairing produces suggestions that must be confirmed, with manual reassignment. Unpaired items stay unpaired and visible. |
| 2.3 | Define one chunked bulk compare endpoint | **Accepted.** `POST /api/v1/compare` takes a list of (application, extractions) items, max 100 per call. |
| 2.4 | Two semaphores can exceed CPU; use one priority-aware limiter | **Accepted.** One capacity limiter sized to workers, with one slot reserved for interactive requests when batch traffic is present. |
| 2.5 | A soft deadline cannot stop a running ONNX call | **Accepted.** Deadline becomes a cooperative pass budget: decide before each pass whether to run it. No fake cancellation. Timeout semantics documented honestly. |
| 2.6 | Relative size vs brand text has no regulatory basis | **Accepted.** For photos: "physical type size not verifiable from an image". For artwork carrying DPI metadata (PNG pHYs, JPEG JFIF/EXIF), compute actual mm from pixel height and compare to the 16.22 table, labeled as metadata-dependent. |
| 2.7 | Cut PDF/GIF expansion | **Partially.** PDF cut. GIF kept: it is one line via Pillow and COLA accepts GIF artwork. |
| 2.8 | Read-only filesystem does not prove no persistence; multipart may spool to /tmp | **Accepted.** Per-file and aggregate caps enforced while streaming; `/tmp` mounted as tmpfs (memory) so nothing reaches disk; disclosed plainly in SECURITY.md. |
| 2.9 | Agreement on local OCR, baked models, no core LLM, traceable findings, human decision | Noted. |

## 3. Over-scope
| # | Finding | Disposition |
|---|---|---|
| 3.1 | Cut profile cleanup, submission note, talking points, branding slot, shortcuts, paste/camera, duplicate detection, report page, print view | **Partially.** All removed from the DoD and moved to a post-core backlog. Exceptions: the submission note and Daniel's talking points are not code and cost minutes; the branding slot is one config line and a sentence in the docs. |
| 3.2 | Cut advanced photo recovery; keep one degraded test | **Accepted, with evidence.** The bake-off showed RapidOCR handles glare, blur, perspective, low contrast and small text with no special preprocessing. Only sideways images failed. Preprocessing is therefore: EXIF transpose, downscale, and a 90-degree retry when confidence is low. Nothing else. |
| 3.3 | One host + tested Docker command + SHA display + final availability check | **Accepted.** A lightweight health monitor stays because it costs nothing and protects the review window. |
| 3.4 | Cut standards of fill and beverage-type inference from core | **Partially.** Beverage type: required field with the sample pre-selected, no inference. Standards of fill: kept, but run against the application's stated net contents (not OCR text), reported as Needs review only, with the January 2025 lists already verified from the eCFR API. Zero OCR risk, one dictionary. |
| 3.5 | DoD #2 reduced to explicit pairing, streaming, triage, export | **Accepted.** Fuzzy suggestions only after the explicit path is reliable. |
| 3.6 | Cut access gate, SBOM, hash-pinned lock, Swagger vendoring, procurement hardening before core | **Accepted.** All to backlog. SECURITY.md still describes the production auth path. `/api/v1/openapi.json` is served; the Swagger UI is not vendored. |
| 3.7 | Reduce docs to README, APPROACH+DECISIONS, REQUIREMENTS_TRACE, LIMITS+SECURITY | **Partially.** Accepted for the deliverable set. AGENTS.md stays (small, and it is the on-theme artifact for an AI-directed engineering role). REGULATIONS.md stays as evidence for the domain rules. THIRD_PARTY_NOTICES stays as a short list. PROCESS folds into APPROACH. |
| 3.8 | If late, cut evidence crops before the core list | **Accepted** as the cut order. Evidence crops are cheap client-side and stay unless time forces it. |

## 4. Technical risks
| # | Finding | Disposition |
|---|---|---|
| 4.1 | Report field recall and false matches, not OCR confidence; add curved/condensed/outlined/gold-on-black/mixed-case brands | **Accepted.** `tools/evaluate.py` reports per-field recall, false-match rate and latency by tier. Generator gains outlined, condensed, arched and mixed-case brand variants. |
| 4.2 | Pin Python 3.12; lock from Linux/amd64, not a Windows 3.13 box | **Accepted, and confirmed by measurement.** On Python 3.13 pip silently resolved RapidOCR to 1.2.3 (2023, v3 models). Local dev moves to 3.12; the lock is generated inside the Docker build. |
| 4.3 | Thread settings may not take effect; verify thread counts and throughput at 1/2/3 | **Accepted, and confirmed.** The 1.2.3 constructor ignores thread kwargs; parallel sessions oversubscribed and throughput did not scale. Fix: current library with explicit ORT session threads, re-measured; process pool with per-worker CPU affinity as the fallback. |
| 4.4 | Measure resident memory per engine and under concurrency | **Accepted.** Numbers go in LIMITS.md. |
| 4.5 | Coordinates: preserve quads, compose all transforms, one canonical oriented space, test 8 EXIF orientations | **Accepted.** |
| 4.6 | Browser EXIF handling may disagree with server orientation | **Accepted.** Server returns oriented dimensions; client decodes with `imageOrientation: "from-image"` and verifies dimensions match, falling back to a server-rendered preview if they do not. |
| 4.7 | USWDS: vendor compiled dist assets with paths intact; test sprite, fonts, CSP | **Accepted.** |
| 4.8 | Azure Container Apps specifics; verify actual cost | **Accepted.** Configured explicitly; cost reported from the portal, not estimated. |
| 4.9 | Per-application latency, two images serial or contended | **Accepted.** Images of one application run in parallel across workers; application-level p50/p95 published. |
| 4.10 | Enforce aggregate and per-file caps while streaming | **Accepted.** |
| 4.11 | "Resume is trivial" is overstated | **Accepted.** Stated plainly: refresh loses the session; export prompt on unload. |
| 4.12 | Pairing ambiguity; require explicit or manual pairing before "ready" | **Accepted.** |
| 4.13 | PDF caps | Moot: PDF cut. |

## 5. Reviewer's-eye check
All six points accepted as framing for the README and the eval. Specifically added: an error
analysis section with representative failures and threshold rationale.

## 6. Domain check
| # | Finding | Disposition |
|---|---|---|
| 6.1 | Encode the full 16.21 text with punctuation; no generic normalizer | **Accepted.** Text verified from the eCFR API on 2026-09-03 (docs/REGULATIONS.md). |
| 6.2 | "Separate and apart" is in 16.21, not 16.22 | **Accepted.** Already correct in REGULATIONS.md; ARCHITECTURE section 10 corrected. |
| 6.3 | Bold rule and type-size thresholds confirmed | Noted; verified from source. |
| 6.4 | Part 16 applies at 0.5% ABV and above | **Accepted.** Documented; not an unconditional rule. |
| 6.5 | Wine ABV may be omitted at 14% or less only with a table/light wine designation (4.36) | **Accepted.** |
| 6.6 | Malt beverage ABV mandatory in some cases (7.63, 7.65) and by state law | **Accepted.** Rule: if the application supplies a value it is checked; if not, the label value is reported for the agent, never flagged as an error. |
| 6.7 | Spirits mandatory information includes name/address; same field of vision rules (5.63) | **Accepted** for name/address (see 1.6). Field-of-vision check deferred to backlog: cheap to detect "found on different images", but not core. |
| 6.8 | Standards of fill: copy current lists, date the source, test new sizes | **Accepted.** Done from the eCFR API text of 5.203 and 4.72 (January 2025 amendments). |
| 6.9 | No fixed sizes for malt does not mean no net-contents rules | **Accepted.** Wording fixed. |
| 6.10 | Country of origin stays a comparison only | **Accepted.** |

## 7. Top five
All five accepted. They are reflected in the revised Definition of Done (ARCHITECTURE.md section 15).

## What the builder pushed back on, for the record
- Standards of fill stays, narrowed to application data (3.4).
- GIF stays (2.7).
- AGENTS.md and REGULATIONS.md stay (3.7).
- A health monitor stays (3.3).
Everything else in the review was accepted or deferred as stated.
