# OCR engine bake-off

_Record of the Day 0 engine bake-off (2026-09-03). Produced with `rapidocr_onnxruntime` 1.2.3 (the version pip resolved on Python 3.13; later replaced by `rapidocr` 3.9.x, see `OCR_EVAL.md`) against Tesseract 5.4 via pytesseract. The measurement scripts were retired after this run; the decision they supported (RapidOCR in, Tesseract out) stands._

Corpus: `tests\fixtures\labels` (46 images). Times are per-image inference on this machine (CPU), images downscaled to 1600 px max side.

## rapidocr

- model load: 0.60 s
- inference ms: median 1058, p95 1716, max 1753
- front hits: brand 95%, class 100%, abv 90%, net 100%
- back: warning similarity median 99 (min 39), bottler 100%

| file | variant | ms | conf | brand | class | abv | net | warn | bottler |
|---|---|---:|---:|---|---|---|---|---:|---|
| APP-001_front_clean.png | clean | 1062 | 0.85 | Y 100 | Y 100 | Y 95 | Y 100 |  |  |
| APP-001_back_clean.png | clean | 1714 | 0.9 |  |  |  |  | 99 | Y 100 |
| APP-001_front_rotate7.png | rotate7 | 1025 | 0.86 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-001_back_blur.png | blur | 1541 | 0.91 |  |  |  |  | 99 | Y 100 |
| APP-001_front_wrong_abv.png | wrong_abv | 461 | 0.84 | Y 100 | Y 100 | Y 87 | Y 100 |  |  |
| APP-002_front_clean.png | clean | 856 | 0.79 | Y 100 | Y 90 | Y 95 | Y 100 |  |  |
| APP-002_back_clean.png | clean | 1474 | 0.9 |  |  |  |  | 100 | Y 100 |
| APP-002_front_glare.png | glare | 513 | 0.8 | Y 100 | Y 90 | Y 95 | Y 100 |  |  |
| APP-002_back_lowcontrast.png | lowcontrast | 1302 | 0.89 |  |  |  |  | 100 | Y 100 |
| APP-002_back_titlecase.png | titlecase | 1275 | 0.92 |  |  |  |  | 99 | Y 100 |
| APP-003_front_clean.png | clean | 581 | 0.81 | Y 100 | Y 100 | Y 93 | Y 100 |  |  |
| APP-003_back_clean.png | clean | 1600 | 0.9 |  |  |  |  | 100 | Y 100 |
| APP-003_front_perspective.png | perspective | 687 | 0.78 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-003_back_small.png | small | 1198 | 0.9 |  |  |  |  | 99 | Y 100 |
| APP-003_back_allbold.png | allbold | 1663 | 0.89 |  |  |  |  | 99 | Y 100 |
| APP-004_front_clean.png | clean | 693 | 0.81 | Y 100 | Y 100 | Y 87 | Y 100 |  |  |
| APP-004_back_clean.png | clean | 1753 | 0.91 |  |  |  |  | 100 | Y 100 |
| APP-004_front_jpeg.png | jpeg | 719 | 0.83 | Y 100 | Y 100 | Y 95 | Y 90 |  |  |
| APP-004_back_rotate90.png | rotate90 | 1700 | 0.9 |  |  |  |  | 47 | Y 100 |
| APP-004_back_altered.png | altered | 1585 | 0.91 |  |  |  |  | 99 | Y 100 |
| APP-005_front_clean.png | clean | 627 | 0.78 | Y 90 | Y 100 | Y 100 | Y 100 |  |  |
| APP-005_back_clean.png | clean | 1724 | 0.89 |  |  |  |  | 99 | Y 100 |
| APP-005_front_rotate7.png | rotate7 | 612 | 0.8 | Y 95 | Y 100 | Y 100 | Y 100 |  |  |
| APP-005_back_blur.png | blur | 1647 | 0.89 |  |  |  |  | 99 | Y 100 |
| APP-005_back_tiny.png | tiny | 1682 | 0.89 |  |  |  |  | 99 | Y 100 |
| APP-006_front_clean.png | clean | 609 | 0.75 | N 80 | Y 100 | Y 86 | Y 100 |  |  |
| APP-006_back_clean.png | clean | 1716 | 0.9 |  |  |  |  | 100 | Y 100 |
| APP-006_front_glare.png | glare | 644 | 0.83 | Y 100 | Y 100 | Y 86 | Y 100 |  |  |
| APP-006_back_lowcontrast.png | lowcontrast | 1647 | 0.9 |  |  |  |  | 90 | Y 100 |
| APP-006_back_missing.png | missing | 1053 | 0.9 |  |  |  |  | 39 | Y 100 |
| APP-007_front_clean.png | clean | 708 | 0.83 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-007_back_clean.png | clean | 1681 | 0.9 |  |  |  |  | 100 | Y 100 |
| APP-007_front_perspective.png | perspective | 492 | 0.84 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-007_back_small.png | small | 1270 | 0.91 |  |  |  |  | 99 | Y 100 |
| APP-008_front_clean.png | clean | 545 | 0.82 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-008_back_clean.png | clean | 1322 | 0.9 |  |  |  |  | 100 | Y 100 |
| APP-008_front_jpeg.png | jpeg | 556 | 0.84 | Y 100 | Y 100 | Y 87 | Y 88 |  |  |
| APP-008_back_rotate90.png | rotate90 | 1451 | 0.9 |  |  |  |  | 52 | Y 100 |
| APP-009_front_clean.png | clean | 933 | 0.79 | Y 100 | Y 95 | Y 100 | Y 100 |  |  |
| APP-009_back_clean.png | clean | 1683 | 0.91 |  |  |  |  | 100 | Y 100 |
| APP-009_front_rotate7.png | rotate7 | 872 | 0.86 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-009_back_blur.png | blur | 1305 | 0.91 |  |  |  |  | 94 | Y 100 |
| APP-010_front_clean.png | clean | 622 | 0.83 | Y 100 | Y 100 | N 84 | Y 100 |  |  |
| APP-010_back_clean.png | clean | 1012 | 0.9 |  |  |  |  | 90 | Y 100 |
| APP-010_front_glare.png | glare | 482 | 0.83 | Y 100 | Y 100 | N 84 | Y 100 |  |  |
| APP-010_back_lowcontrast.png | lowcontrast | 991 | 0.9 |  |  |  |  | 90 | Y 100 |

## tesseract-psm6

- model load: 0.01 s
- inference ms: median 346, p95 574, max 726
- front hits: brand 95%, class 100%, abv 76%, net 71%
- back: warning similarity median 100 (min 34), bottler 92%

| file | variant | ms | conf | brand | class | abv | net | warn | bottler |
|---|---|---:|---:|---|---|---|---|---:|---|
| APP-001_front_clean.png | clean | 316 | 0.95 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-001_back_clean.png | clean | 397 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-001_front_rotate7.png | rotate7 | 306 | 0.87 | Y 88 | Y 100 | Y 95 | Y 100 |  |  |
| APP-001_back_blur.png | blur | 425 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-001_front_wrong_abv.png | wrong_abv | 270 | 0.95 | Y 100 | Y 100 | Y 91 | Y 100 |  |  |
| APP-002_front_clean.png | clean | 235 | 0.94 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-002_back_clean.png | clean | 371 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-002_front_glare.png | glare | 257 | 0.94 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-002_back_lowcontrast.png | lowcontrast | 377 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-002_back_titlecase.png | titlecase | 364 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-003_front_clean.png | clean | 265 | 0.94 | Y 100 | Y 100 | Y 100 | N 80 |  |  |
| APP-003_back_clean.png | clean | 471 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-003_front_perspective.png | perspective | 268 | 0.94 | Y 100 | Y 100 | Y 100 | N 80 |  |  |
| APP-003_back_small.png | small | 339 | 0.85 |  |  |  |  | 98 | Y 100 |
| APP-003_back_allbold.png | allbold | 491 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-004_front_clean.png | clean | 299 | 0.91 | Y 100 | Y 100 | Y 100 | Y 90 |  |  |
| APP-004_back_clean.png | clean | 578 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-004_front_jpeg.png | jpeg | 281 | 0.89 | Y 100 | Y 100 | Y 100 | Y 90 |  |  |
| APP-004_back_rotate90.png | rotate90 | 611 | 0.37 |  |  |  |  | 35 | N 37 |
| APP-004_back_altered.png | altered | 564 | 0.95 |  |  |  |  | 99 | Y 100 |
| APP-005_front_clean.png | clean | 234 | 0.96 | Y 100 | Y 100 | N 28 | N 33 |  |  |
| APP-005_back_clean.png | clean | 404 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-005_front_rotate7.png | rotate7 | 334 | 0.96 | Y 100 | Y 100 | N 28 | N 33 |  |  |
| APP-005_back_blur.png | blur | 432 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-005_back_tiny.png | tiny | 352 | 0.92 |  |  |  |  | 96 | Y 100 |
| APP-006_front_clean.png | clean | 305 | 0.96 | Y 100 | Y 100 | N 23 | N 25 |  |  |
| APP-006_back_clean.png | clean | 436 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-006_front_glare.png | glare | 248 | 0.96 | Y 100 | Y 100 | N 23 | N 25 |  |  |
| APP-006_back_lowcontrast.png | lowcontrast | 400 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-006_back_missing.png | missing | 270 | 0.95 |  |  |  |  | 39 | Y 100 |
| APP-007_front_clean.png | clean | 294 | 0.86 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-007_back_clean.png | clean | 452 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-007_front_perspective.png | perspective | 350 | 0.87 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-007_back_small.png | small | 342 | 0.9 |  |  |  |  | 99 | Y 100 |
| APP-008_front_clean.png | clean | 228 | 0.94 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-008_back_clean.png | clean | 480 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-008_front_jpeg.png | jpeg | 313 | 0.94 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-008_back_rotate90.png | rotate90 | 726 | 0.41 |  |  |  |  | 34 | N 34 |
| APP-009_front_clean.png | clean | 286 | 0.95 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-009_back_clean.png | clean | 484 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-009_front_rotate7.png | rotate7 | 323 | 0.83 | N 86 | Y 100 | N 83 | Y 100 |  |  |
| APP-009_back_blur.png | blur | 509 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-010_front_clean.png | clean | 228 | 0.93 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-010_back_clean.png | clean | 362 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-010_front_glare.png | glare | 253 | 0.93 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-010_back_lowcontrast.png | lowcontrast | 400 | 0.96 |  |  |  |  | 100 | Y 100 |

## tesseract-psm11

- model load: 0.00 s
- inference ms: median 348, p95 569, max 632
- front hits: brand 86%, class 95%, abv 81%, net 52%
- back: warning similarity median 100 (min 35), bottler 88%

| file | variant | ms | conf | brand | class | abv | net | warn | bottler |
|---|---|---:|---:|---|---|---|---|---:|---|
| APP-001_front_clean.png | clean | 254 | 0.9 | Y 100 | Y 100 | Y 100 | N 83 |  |  |
| APP-001_back_clean.png | clean | 415 | 0.94 |  |  |  |  | 100 | Y 100 |
| APP-001_front_rotate7.png | rotate7 | 293 | 0.77 | N 61 | N 48 | N 84 | N 50 |  |  |
| APP-001_back_blur.png | blur | 397 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-001_front_wrong_abv.png | wrong_abv | 253 | 0.95 | Y 100 | Y 100 | Y 91 | Y 100 |  |  |
| APP-002_front_clean.png | clean | 232 | 0.94 | Y 100 | Y 100 | Y 100 | N 50 |  |  |
| APP-002_back_clean.png | clean | 353 | 0.94 |  |  |  |  | 100 | Y 100 |
| APP-002_front_glare.png | glare | 231 | 0.94 | Y 100 | Y 100 | Y 100 | N 50 |  |  |
| APP-002_back_lowcontrast.png | lowcontrast | 360 | 0.94 |  |  |  |  | 100 | Y 100 |
| APP-002_back_titlecase.png | titlecase | 374 | 0.94 |  |  |  |  | 100 | Y 100 |
| APP-003_front_clean.png | clean | 224 | 0.95 | N 58 | Y 100 | Y 100 | N 66 |  |  |
| APP-003_back_clean.png | clean | 526 | 0.94 |  |  |  |  | 100 | Y 100 |
| APP-003_front_perspective.png | perspective | 262 | 0.92 | Y 100 | Y 100 | Y 93 | N 80 |  |  |
| APP-003_back_small.png | small | 342 | 0.85 |  |  |  |  | 98 | N 69 |
| APP-003_back_allbold.png | allbold | 532 | 0.94 |  |  |  |  | 100 | Y 100 |
| APP-004_front_clean.png | clean | 252 | 0.83 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-004_back_clean.png | clean | 581 | 0.94 |  |  |  |  | 100 | Y 100 |
| APP-004_front_jpeg.png | jpeg | 270 | 0.89 | Y 100 | Y 100 | Y 100 | N 50 |  |  |
| APP-004_back_rotate90.png | rotate90 | 450 | 0.38 |  |  |  |  | 35 | N 34 |
| APP-004_back_altered.png | altered | 512 | 0.94 |  |  |  |  | 99 | Y 100 |
| APP-005_front_clean.png | clean | 231 | 0.95 | Y 100 | Y 100 | Y 94 | Y 100 |  |  |
| APP-005_back_clean.png | clean | 395 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-005_front_rotate7.png | rotate7 | 286 | 0.89 | Y 90 | Y 100 | N 83 | Y 100 |  |  |
| APP-005_back_blur.png | blur | 434 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-005_back_tiny.png | tiny | 363 | 0.94 |  |  |  |  | 93 | Y 100 |
| APP-006_front_clean.png | clean | 228 | 0.94 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-006_back_clean.png | clean | 391 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-006_front_glare.png | glare | 249 | 0.94 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-006_back_lowcontrast.png | lowcontrast | 424 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-006_back_missing.png | missing | 304 | 0.93 |  |  |  |  | 39 | Y 100 |
| APP-007_front_clean.png | clean | 236 | 0.94 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-007_back_clean.png | clean | 408 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-007_front_perspective.png | perspective | 270 | 0.9 | Y 92 | Y 100 | Y 100 | Y 96 |  |  |
| APP-007_back_small.png | small | 289 | 0.84 |  |  |  |  | 97 | Y 91 |
| APP-008_front_clean.png | clean | 230 | 0.95 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-008_back_clean.png | clean | 522 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-008_front_jpeg.png | jpeg | 238 | 0.68 | Y 100 | Y 100 | Y 100 | N 77 |  |  |
| APP-008_back_rotate90.png | rotate90 | 460 | 0.36 |  |  |  |  | 37 | N 40 |
| APP-009_front_clean.png | clean | 262 | 0.89 | Y 100 | Y 100 | N 55 | N 50 |  |  |
| APP-009_back_clean.png | clean | 632 | 0.95 |  |  |  |  | 100 | Y 100 |
| APP-009_front_rotate7.png | rotate7 | 494 | 0.76 | N 59 | Y 90 | N 76 | N 50 |  |  |
| APP-009_back_blur.png | blur | 621 | 0.96 |  |  |  |  | 100 | Y 100 |
| APP-010_front_clean.png | clean | 218 | 0.94 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-010_back_clean.png | clean | 371 | 0.94 |  |  |  |  | 100 | Y 100 |
| APP-010_front_glare.png | glare | 235 | 0.94 | Y 100 | Y 100 | Y 100 | Y 100 |  |  |
| APP-010_back_lowcontrast.png | lowcontrast | 414 | 0.94 |  |  |  |  | 100 | Y 100 |
