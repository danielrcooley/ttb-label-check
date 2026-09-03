#!/usr/bin/env python
"""Parametric OCR evaluation for rapidocr 3.x: accuracy, latency and concurrency.

Examples:
    # accuracy + latency, single session
    python tools/ocr_eval2.py --labels tests/fixtures/labels --tag v6small-cls --params '{"Global.use_cls": true}'
    # thread-pool concurrency, one engine per thread, 1 intra-op thread each
    python tools/ocr_eval2.py --labels tests/fixtures/labels --tag v6small --mode threads --workers 2 \
        --params '{"Global.use_cls": false, "EngineConfig.onnxruntime.intra_op_num_threads": 1}'
    # process-pool concurrency, one engine per process
    python tools/ocr_eval2.py --labels tests/fixtures/labels --tag v6small --mode procs --workers 2 --params '{...}'

Appends one summary block per run to --report (default docs/OCR_EVAL.md).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import threading
import time
import unicodedata
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

MAX_SIDE = 1600
_ENGINE = None  # per-process engine for the process-pool mode


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("`", "'")
    return re.sub(r"\s+", " ", s).casefold().strip()


def load(path: Path, max_side: int = MAX_SIDE) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    s = max_side / max(w, h)
    if s < 1:
        im = im.resize((int(w * s), int(h * s)), Image.LANCZOS)
    return np.asarray(im)


def make_engine(params: dict):
    """Build a RapidOCR engine; string values for enum-typed keys are converted."""
    from rapidocr import RapidOCR

    p = dict(params or {})
    try:
        from rapidocr import EngineType, LangDet, LangRec, ModelType, OCRVersion

        enum_map = {
            "Det.ocr_version": OCRVersion,
            "Rec.ocr_version": OCRVersion,
            "Cls.ocr_version": OCRVersion,
            "Det.model_type": ModelType,
            "Rec.model_type": ModelType,
            "Cls.model_type": ModelType,
            "Det.lang_type": LangDet,
            "Rec.lang_type": LangRec,
            "Cls.lang_type": LangDet,
            "Det.engine_type": EngineType,
            "Rec.engine_type": EngineType,
            "Cls.engine_type": EngineType,
        }
        for k, enum_cls in enum_map.items():
            if k in p and isinstance(p[k], str):
                p[k] = enum_cls(p[k])
    except ImportError:
        pass
    return RapidOCR(params=p or None)


def run_engine(eng, arr: np.ndarray) -> tuple[str, float, float]:
    t0 = time.perf_counter()
    r = eng(arr)
    dt = (time.perf_counter() - t0) * 1000
    txts = list(r.txts) if getattr(r, "txts", None) else []
    scores = list(r.scores) if getattr(r, "scores", None) else []
    return "\n".join(txts), (statistics.fmean(scores) if scores else 0.0), dt


def _proc_init(params_json: str) -> None:
    global _ENGINE
    _ENGINE = make_engine(json.loads(params_json))
    _ENGINE(np.full((64, 256, 3), 255, dtype=np.uint8))  # warm


def _proc_job(path: str) -> tuple[str, str, float, float]:
    text, conf, dt = run_engine(_ENGINE, load(Path(path)))
    return path, text, conf, dt


def score_row(app: dict, img: dict, text: str, warning: str) -> dict:
    from rapidfuzz import fuzz

    def hit(needle: str, thresh: int) -> tuple[bool, int]:
        sc = int(fuzz.partial_ratio(normalize(needle), normalize(text)))
        return sc >= thresh, sc

    row: dict = {}
    if img["side"] == "front":
        row["brand"] = hit(app["brand"], 88)
        row["class"] = hit(app["class_type"], 88)
        row["abv"] = hit(app["alcohol_content"], 85)
        row["net"] = hit(app["net_contents"], 85)
    else:
        row["warning"] = int(fuzz.partial_ratio(normalize(warning), normalize(text)))
        row["bottler"] = hit(app["bottler"], 85)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--params", default="{}")
    ap.add_argument("--mode", default="single", choices=["single", "threads", "procs"])
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--report", default="docs/OCR_EVAL.md")
    ap.add_argument("--max-side", type=int, default=MAX_SIDE)
    args = ap.parse_args()

    params = json.loads(args.params)
    labels = Path(args.labels)
    manifest = json.loads((labels / "manifest.json").read_text(encoding="utf-8"))
    warning = manifest["warning_text"]
    items = [(app, img) for app in manifest["applications"] for img in app["images"]]
    paths = [labels / img["file"] for _, img in items]

    t_init = time.perf_counter()
    results: dict[str, tuple[str, float, float]] = {}
    if args.mode == "single":
        eng = make_engine(params)
        eng(load(paths[0], args.max_side))  # warm
        init_s = time.perf_counter() - t_init
        t0 = time.perf_counter()
        for p in paths:
            results[str(p)] = run_engine(eng, load(p, args.max_side))
        wall = time.perf_counter() - t0
    elif args.mode == "threads":
        local = threading.local()

        def get():
            if not hasattr(local, "eng"):
                local.eng = make_engine(params)
                local.eng(np.full((64, 256, 3), 255, dtype=np.uint8))
            return local.eng

        def job(p: Path):
            return str(p), run_engine(get(), load(p, args.max_side))

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(lambda _: get(), range(args.workers)))
            init_s = time.perf_counter() - t_init
            t0 = time.perf_counter()
            for k, v in ex.map(job, paths):
                results[k] = v
            wall = time.perf_counter() - t0
    else:
        with ProcessPoolExecutor(
            max_workers=args.workers, initializer=_proc_init, initargs=(json.dumps(params),)
        ) as ex:
            list(ex.map(_proc_job, [str(paths[0])] * args.workers))  # force init in every worker
            init_s = time.perf_counter() - t_init
            t0 = time.perf_counter()
            for k, text, conf, dt in ex.map(_proc_job, [str(p) for p in paths]):
                results[k] = (text, conf, dt)
            wall = time.perf_counter() - t0

    rows = []
    for (app, img), p in zip(items, paths, strict=True):
        text, conf, dt = results[str(p)]
        rows.append(
            {
                "file": img["file"],
                "side": img["side"],
                "variant": img["variant"],
                "ms": round(dt),
                "conf": round(conf, 2),
                **score_row(app, img, text, warning),
            }
        )

    ms = [r["ms"] for r in rows]
    fronts = [r for r in rows if r["side"] == "front"]
    backs = [r for r in rows if r["side"] == "back"]

    def rate(key, subset):
        vals = [r[key][0] for r in subset if key in r]
        return f"{100 * sum(vals) / len(vals):.0f}%" if vals else "n/a"

    wsims = [r["warning"] for r in backs]
    summary = [
        f"## {args.tag} | mode={args.mode} workers={args.workers} max_side={args.max_side} cpu={os.cpu_count()}",
        f"params: `{json.dumps(params)}`",
        f"- init+warm {init_s:.1f} s; per-image ms median {statistics.median(ms):.0f}, "
        f"p95 {np.percentile(ms, 95):.0f}, max {max(ms)}; wall {wall:.1f} s; "
        f"throughput {len(rows) / wall:.2f} img/s",
        f"- front hits: brand {rate('brand', fronts)}, class {rate('class', fronts)}, "
        f"abv {rate('abv', fronts)}, net {rate('net', fronts)}",
        f"- back: warning sim median {statistics.median(wsims):.0f} (min {min(wsims)}), "
        f"bottler {rate('bottler', backs)}",
        "- misses: "
        + (
            ", ".join(
                f"{r['file']}[{k}={r[k][1]}]"
                for r in rows
                for k in ("brand", "class", "abv", "net", "bottler")
                if k in r and not r[k][0]
            )
            or "none"
        )
        + "; warning<90: "
        + (", ".join(f"{r['file']}[{r['warning']}]" for r in backs if r["warning"] < 90) or "none"),
        "",
    ]
    print("\n".join(summary))
    rp = Path(args.report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    with rp.open("a", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")


if __name__ == "__main__":
    main()
