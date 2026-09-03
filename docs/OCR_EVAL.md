# OCR evaluation log (rapidocr 3.9.2, ONNX Runtime 1.29)

_Corpus: 46 synthetic label images (10 fictional applications; clean, degraded and problem variants). Machine: 16-logical-CPU Windows laptop. "Hits" = the application value is recoverable from the OCR text (fuzzy partial ratio >= 85-88); "warning sim" = similarity of the OCR text to the 27 CFR 16.21 statement. Every run appends a block below. Sideways (rotate90) images fail in every configuration by design of the test; the app handles them with a 90-degree retry. The "missing" back label is expected to score ~39._

## Conclusion (2026-09-03)

**Chosen configuration:** bundled PP-OCRv6 small detector + recognizer (Chinese-trained multilingual set, handles Latin text), angle classifier off, `Det.limit_side_len=640`, input downscaled to 1280 px max side, `Rec.rec_batch_num=16`, one ONNX intra-op thread per engine, one engine per worker thread, N workers = vCPUs. Models vendored in `app/models/` with SHA-256 (`MANIFEST.json`); nothing downloads at build or run.

| Run | Config | ms/img (median, single thread unless noted) | brand | class | abv | net | warning sim | notes |
|---|---|---:|---|---|---|---|---|---|
| A | v6 small, cls on, all threads | 926 (16 threads) | 95% | 100% | 100% | 90% | 100 | baseline |
| B | v4 mobile ch, cls off, all threads | 1366 (16 threads) | 100% | 90% | 100% | 95% | 100 | slower, class misses |
| C | v4 det + v4 EN rec, all threads | 1496 (16 threads) | 100% | 100% | 100% | 100% | 99 | best hits, slowest |
| D | A config, 1 thread | 2429 | 95% | 100% | 100% | 90% | 100 | single-core truth |
| E | A config, 2 threads | 1400 | | | | | | 1.7x from 2 threads |
| F | v6 det + v4 EN rec | 1400 (16 thr) / 3878 (1 thr) | 90% | 100% | 100% | 100% | 99 | EN rec is slow single-threaded |
| G | **A config + det 640 + side 1280 + batch 16, 1 thread** | **1958** | 95% | 100% | 100% | 90% | 100 | **chosen**; 19% faster than D, same accuracy |
| H | F config + same levers, 1 thread | 3314 | 95% | 100% | 100% | 100% | 99 | too slow |
| T2/T4 | A config, 1 thread each, thread pool of 2 / 4 | 2600 / 3069 per img | | | | | | throughput 0.79 / 1.33 img/s (1.84x / 3.1x of one worker) |
| P2/P4 | same, process pool | 2645 / 3080 per img | | | | | | throughput 0.79 / 1.31 img/s: identical to threads |

The single remaining "miss" in the chosen config is net contents "1 L" on one product, a scoring artifact of fuzzy matching a three-character string; the application parses net contents with a dedicated unit parser, not fuzzy text, so this does not carry into the product. Brand misses are the arched or rotated decorative brand at 83-85 similarity, which the product reports as Needs review rather than a miss.

---

## A-v6small-ch-cls | mode=single workers=1 max_side=1600 cpu=16
params: `{}`
- init+warm 1.6 s; per-image ms median 926, p95 1109, max 1198; wall 41.6 s; throughput 1.11 img/s
- front hits: brand 95%, class 100%, abv 100%, net 90%
- back: warning sim median 100 (min 39), bottler 100%
- misses: APP-003_front_clean.png[net=80], APP-003_front_perspective.png[net=80], APP-005_front_rotate7.png[brand=85]; warning<90: APP-003_back_small.png[80], APP-004_back_rotate90.png[54], APP-006_back_missing.png[39], APP-008_back_rotate90.png[60]

## B-v4mobile-ch-nocls | mode=single workers=1 max_side=1600 cpu=16
params: `{"Global.use_cls": false, "Det.ocr_version": "PP-OCRv4", "Det.model_type": "mobile", "Rec.ocr_version": "PP-OCRv4", "Rec.model_type": "mobile"}`
- init+warm 16.7 s; per-image ms median 1366, p95 2127, max 2182; wall 62.0 s; throughput 0.74 img/s
- front hits: brand 100%, class 90%, abv 100%, net 95%
- back: warning sim median 100 (min 39), bottler 92%
- misses: APP-003_front_clean.png[net=80], APP-004_back_rotate90.png[bottler=37], APP-007_front_clean.png[class=85], APP-007_front_perspective.png[class=85], APP-008_back_rotate90.png[bottler=28]; warning<90: APP-003_back_small.png[75], APP-004_back_rotate90.png[39], APP-006_back_missing.png[39], APP-007_back_small.png[79], APP-008_back_rotate90.png[42]

## C-v4det-ch_v4rec-EN-nocls | mode=single workers=1 max_side=1600 cpu=16
params: `{"Global.use_cls": false, "Det.ocr_version": "PP-OCRv4", "Det.model_type": "mobile", "Rec.ocr_version": "PP-OCRv4", "Rec.model_type": "mobile", "Rec.lang_type": "en"}`
- init+warm 10.2 s; per-image ms median 1496, p95 2121, max 2196; wall 65.5 s; throughput 0.70 img/s
- front hits: brand 100%, class 100%, abv 100%, net 100%
- back: warning sim median 99 (min 39), bottler 92%
- misses: APP-004_back_rotate90.png[bottler=32], APP-008_back_rotate90.png[bottler=31]; warning<90: APP-003_back_small.png[81], APP-004_back_rotate90.png[40], APP-006_back_missing.png[39], APP-007_back_small.png[81], APP-008_back_rotate90.png[40]

## D-v6small-ch-nocls-intra1 | mode=single workers=1 max_side=1600 cpu=16
params: `{"Global.use_cls": false, "EngineConfig.onnxruntime.intra_op_num_threads": 1, "EngineConfig.onnxruntime.inter_op_num_threads": 1}`
- init+warm 3.1 s; per-image ms median 2429, p95 2892, max 2942; wall 106.6 s; throughput 0.43 img/s
- front hits: brand 95%, class 100%, abv 100%, net 90%
- back: warning sim median 100 (min 39), bottler 92%
- misses: APP-003_front_clean.png[net=80], APP-003_front_perspective.png[net=80], APP-004_back_rotate90.png[bottler=45], APP-005_front_rotate7.png[brand=85], APP-008_back_rotate90.png[bottler=44]; warning<90: APP-003_back_small.png[80], APP-004_back_rotate90.png[41], APP-006_back_missing.png[39], APP-008_back_rotate90.png[43]

## T-threads | mode=threads workers=2 max_side=1600 cpu=16
params: `{"Global.use_cls": false, "EngineConfig.onnxruntime.intra_op_num_threads": 1, "EngineConfig.onnxruntime.inter_op_num_threads": 1}`
- init+warm 3.4 s; per-image ms median 2600, p95 3064, max 3281; wall 58.4 s; throughput 0.79 img/s
- front hits: brand 95%, class 100%, abv 100%, net 90%
- back: warning sim median 100 (min 39), bottler 92%
- misses: APP-003_front_clean.png[net=80], APP-003_front_perspective.png[net=80], APP-004_back_rotate90.png[bottler=45], APP-005_front_rotate7.png[brand=85], APP-008_back_rotate90.png[bottler=44]; warning<90: APP-003_back_small.png[80], APP-004_back_rotate90.png[41], APP-006_back_missing.png[39], APP-008_back_rotate90.png[43]

## T-threads | mode=threads workers=4 max_side=1600 cpu=16
params: `{"Global.use_cls": false, "EngineConfig.onnxruntime.intra_op_num_threads": 1, "EngineConfig.onnxruntime.inter_op_num_threads": 1}`
- init+warm 4.3 s; per-image ms median 3069, p95 3582, max 4145; wall 34.7 s; throughput 1.33 img/s
- front hits: brand 95%, class 100%, abv 100%, net 90%
- back: warning sim median 100 (min 39), bottler 92%
- misses: APP-003_front_clean.png[net=80], APP-003_front_perspective.png[net=80], APP-004_back_rotate90.png[bottler=45], APP-005_front_rotate7.png[brand=85], APP-008_back_rotate90.png[bottler=44]; warning<90: APP-003_back_small.png[80], APP-004_back_rotate90.png[41], APP-006_back_missing.png[39], APP-008_back_rotate90.png[43]

## P-procs | mode=procs workers=2 max_side=1600 cpu=16
params: `{"Global.use_cls": false, "EngineConfig.onnxruntime.intra_op_num_threads": 1, "EngineConfig.onnxruntime.inter_op_num_threads": 1}`
- init+warm 5.3 s; per-image ms median 2645, p95 3059, max 3127; wall 58.0 s; throughput 0.79 img/s
- front hits: brand 95%, class 100%, abv 100%, net 90%
- back: warning sim median 100 (min 39), bottler 92%
- misses: APP-003_front_clean.png[net=80], APP-003_front_perspective.png[net=80], APP-004_back_rotate90.png[bottler=45], APP-005_front_rotate7.png[brand=85], APP-008_back_rotate90.png[bottler=44]; warning<90: APP-003_back_small.png[80], APP-004_back_rotate90.png[41], APP-006_back_missing.png[39], APP-008_back_rotate90.png[43]

## P-procs | mode=procs workers=4 max_side=1600 cpu=16
params: `{"Global.use_cls": false, "EngineConfig.onnxruntime.intra_op_num_threads": 1, "EngineConfig.onnxruntime.inter_op_num_threads": 1}`
- init+warm 6.6 s; per-image ms median 3080, p95 3683, max 3768; wall 35.1 s; throughput 1.31 img/s
- front hits: brand 95%, class 100%, abv 100%, net 90%
- back: warning sim median 100 (min 39), bottler 92%
- misses: APP-003_front_clean.png[net=80], APP-003_front_perspective.png[net=80], APP-004_back_rotate90.png[bottler=45], APP-005_front_rotate7.png[brand=85], APP-008_back_rotate90.png[bottler=44]; warning<90: APP-003_back_small.png[80], APP-004_back_rotate90.png[41], APP-006_back_missing.png[39], APP-008_back_rotate90.png[43]

## E-v6small-intra2 | mode=single workers=1 max_side=1600 cpu=16
params: `{"Global.use_cls": false, "EngineConfig.onnxruntime.intra_op_num_threads": 2, "EngineConfig.onnxruntime.inter_op_num_threads": 1}`
- init+warm 2.4 s; per-image ms median 1400, p95 1662, max 1678; wall 61.3 s; throughput 0.75 img/s
- front hits: brand 95%, class 100%, abv 100%, net 90%
- back: warning sim median 100 (min 39), bottler 92%
- misses: APP-003_front_clean.png[net=80], APP-003_front_perspective.png[net=80], APP-004_back_rotate90.png[bottler=45], APP-005_front_rotate7.png[brand=85], APP-008_back_rotate90.png[bottler=44]; warning<90: APP-003_back_small.png[80], APP-004_back_rotate90.png[41], APP-006_back_missing.png[39], APP-008_back_rotate90.png[43]

## F-v6det_v4recEN-nocls | mode=single workers=1 max_side=1600 cpu=16
params: `{"Global.use_cls": false, "Rec.ocr_version": "PP-OCRv4", "Rec.model_type": "mobile", "Rec.lang_type": "en"}`
- init+warm 2.4 s; per-image ms median 1400, p95 2031, max 2118; wall 61.8 s; throughput 0.74 img/s
- front hits: brand 90%, class 100%, abv 100%, net 100%
- back: warning sim median 99 (min 35), bottler 92%
- misses: APP-004_back_rotate90.png[bottler=35], APP-005_front_rotate7.png[brand=83], APP-008_front_clean.png[brand=80], APP-008_back_rotate90.png[bottler=32]; warning<90: APP-003_back_small.png[80], APP-004_back_rotate90.png[35], APP-006_back_missing.png[39], APP-008_back_rotate90.png[38]

## F-intra1 | mode=single workers=1 max_side=1600 cpu=16
params: `{"Global.use_cls": false, "Rec.ocr_version": "PP-OCRv4", "Rec.model_type": "mobile", "Rec.lang_type": "en", "EngineConfig.onnxruntime.intra_op_num_threads": 1, "EngineConfig.onnxruntime.inter_op_num_threads": 1}`
- init+warm 3.4 s; per-image ms median 3878, p95 4848, max 4976; wall 156.9 s; throughput 0.29 img/s
- front hits: brand 90%, class 100%, abv 100%, net 100%
- back: warning sim median 99 (min 35), bottler 92%
- misses: APP-004_back_rotate90.png[bottler=35], APP-005_front_rotate7.png[brand=83], APP-008_front_clean.png[brand=80], APP-008_back_rotate90.png[bottler=32]; warning<90: APP-003_back_small.png[80], APP-004_back_rotate90.png[35], APP-006_back_missing.png[39], APP-008_back_rotate90.png[38]

## G-A-intra1-det640-side1280 | mode=single workers=1 max_side=1280 cpu=16
params: `{"Global.use_cls": false, "Det.limit_side_len": 640, "Rec.rec_batch_num": 16, "EngineConfig.onnxruntime.intra_op_num_threads": 1, "EngineConfig.onnxruntime.inter_op_num_threads": 1}`
- init+warm 2.1 s; per-image ms median 1958, p95 2276, max 2603; wall 81.0 s; throughput 0.57 img/s
- front hits: brand 95%, class 100%, abv 100%, net 90%
- back: warning sim median 100 (min 39), bottler 92%
- misses: APP-003_front_clean.png[net=80], APP-003_front_perspective.png[net=80], APP-004_back_rotate90.png[bottler=49], APP-005_front_rotate7.png[brand=85], APP-008_back_rotate90.png[bottler=42]; warning<90: APP-003_back_small.png[87], APP-004_back_rotate90.png[41], APP-006_back_missing.png[39], APP-007_back_small.png[81], APP-008_back_rotate90.png[43]

## H-F-intra1-det640-side1280 | mode=single workers=1 max_side=1280 cpu=16
params: `{"Global.use_cls": false, "Rec.ocr_version": "PP-OCRv4", "Rec.model_type": "mobile", "Rec.lang_type": "en", "Det.limit_side_len": 640, "Rec.rec_batch_num": 16, "EngineConfig.onnxruntime.intra_op_num_threads": 1, "EngineConfig.onnxruntime.inter_op_num_threads": 1}`
- init+warm 3.3 s; per-image ms median 3314, p95 4739, max 5475; wall 138.5 s; throughput 0.33 img/s
- front hits: brand 95%, class 100%, abv 100%, net 100%
- back: warning sim median 99 (min 34), bottler 92%
- misses: APP-004_back_rotate90.png[bottler=30], APP-005_front_rotate7.png[brand=85], APP-008_back_rotate90.png[bottler=29]; warning<90: APP-003_back_small.png[87], APP-004_back_rotate90.png[35], APP-006_back_missing.png[39], APP-007_back_small.png[81], APP-008_back_rotate90.png[34]

