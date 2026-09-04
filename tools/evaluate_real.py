#!/usr/bin/env python
"""Real-world evaluation on approved COLAs fetched by tools/cola_fetch.py.

The COLA form carries brand name, class/type, origin and the applicant's name and address, but not
alcohol content or net contents, so this runs the extraction path (no application needed) and
scores what the registry knows:

- brand name, class/type description, applicant name: the product's own matcher (best_span +
  status_for) against the OCR lines, reported as Match / Needs review / Mismatch / Not found;
- country of origin, imports only: the country name found on the label (fuzzy, partial);
- government warning: the product's warning comparator, reported as exact / case / noise /
  wording / absent, plus the capital-letters check on the heading;
- alcohol content and net contents: whether a statement was read at all;
- per-record latency, image count and image size.

Writes docs/EVAL_REAL.md (aggregate numbers only) and <real>/results.csv (per record, for hand
review; stays local with the images).

Usage:
    python tools/evaluate_real.py [--real tests/fixtures/real] [--workers 2] [--out docs/EVAL_REAL.md]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.ocr.pool import OcrPool
from app.ocr.rapid import RapidEngine
from app.pipeline.compare import bottler_check
from app.pipeline.match import best_span, status_for
from app.pipeline.normalize import fold
from app.pipeline.warning import build_report
from app.schemas import OcrLine
from app.services import Upload, extract

Record = dict[str, Any]


def _fit(path: Path, max_pixels: int) -> bytes:
    """The registry occasionally stores artwork above the product's 25 MP limit (the product answers
    413 and asks for a smaller file). For the evaluation, do what the user would: shrink it."""
    from io import BytesIO

    from PIL import Image

    data = path.read_bytes()
    with Image.open(BytesIO(data)) as im:
        w, h = im.size
        if w * h <= max_pixels:
            return data
        scale = (max_pixels / (w * h)) ** 0.5 * 0.98
        im = im.convert("RGB").resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, "PNG")
        print(f"{path.name}: {w}x{h} shrunk to fit {max_pixels // 1_000_000} MP", flush=True)
        return buf.getvalue()


def _status(expected: str, lines: list[OcrLine], s: Settings) -> tuple[str, str, int | None]:
    cand = best_span(expected, lines)
    st, _ = status_for(cand, expected, review_at=s.match_review_threshold, mismatch_at=s.match_mismatch_threshold)
    return str(st), (cand.text if cand else ""), (int(cand.score) if cand else None)


def _applicant_status(registered: str, lines: list[OcrLine], s: Settings) -> tuple[str, str, int | None]:
    """The product's own bottler check on the registry's item 8 line, exactly as the batch screen
    would receive it from a spreadsheet (names, address and the name used on the label, comma
    separated)."""
    check = bottler_check(registered, lines, s)
    return str(check.status), check.found or "", int(check.score) if check.score is not None else None


async def run(real: Path, workers: int) -> tuple[list[Record], Record]:
    settings = Settings(ocr_workers=workers)
    pool = OcrPool(settings, lambda: RapidEngine(settings))
    pool.warmup()
    with (real / "cola.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    results: list[Record] = []
    for row in rows:
        files = [n for n in row["images"].split(";") if n and (real / n).exists()]
        if not files:
            continue
        uploads = [Upload(data=_fit(real / n, settings.max_image_pixels), filename=n) for n in files]
        t0 = time.perf_counter()
        res = await extract(uploads, settings, pool, interactive=True)
        ms = int((time.perf_counter() - t0) * 1000)
        lines = res.lines
        applicant_line = ", ".join(part.strip() for part in row["applicant"].split(" | ") if part.strip())
        rec: Record = {
            "ttbid": row["ttbid"],
            "beverage_type": row["beverage_type"],
            "images": len(files),
            "long_side_px": max((max(im.width, im.height) for im in res.images), default=0),
            "readable": all(im.quality.readable for im in res.images),
            "rotated": any(im.rotated_degrees for im in res.images),
            "lines": len(lines),
            "ms": ms,
        }
        for field, expected in (("brand", row["brand"]), ("class_desc", row["class_desc"])):
            st, found, score = _status(expected, lines, settings) if expected else ("n/a", "", None)
            rec[f"{field}_status"], rec[f"{field}_found"], rec[f"{field}_score"] = st, found, score
            rec[f"{field}_expected"] = expected
        st, found, score = _applicant_status(applicant_line, lines, settings) if applicant_line else ("n/a", "", None)
        rec["applicant_name_status"], rec["applicant_name_found"], rec["applicant_name_score"] = st, found, score
        rec["applicant_name_expected"] = applicant_line
        if row["domestic"] == "no" and row["origin_desc"]:
            country = fold(row["origin_desc"])
            rec["origin_found"] = any(fuzz.partial_ratio(country, fold(ln.text)) >= 90 for ln in lines)
        else:
            rec["origin_found"] = None
        w = build_report(lines, mismatch_similarity=settings.warning_mismatch_similarity)
        rec.update(
            {
                "warning_present": w.present,
                "warning_assessment": w.assessment,
                "warning_anchor_caps": str(w.anchor_caps),
                "warning_similarity": round(w.similarity, 3) if w.similarity is not None else None,
                "warning_diff": (w.diff or "")[:300],
                "alcohol_read": res.fields.alcohol_percent is not None,
                "alcohol_percent": res.fields.alcohol_percent,
                "net_read": bool(res.fields.net_contents_ml),
                "net_ml": ";".join(f"{v:g}" for v in res.fields.net_contents_ml),
            }
        )
        results.append(rec)
        print(
            f"{rec['ttbid']} {rec['beverage_type']:7s} {rec['images']} img {rec['ms']:5d} ms  brand={rec['brand_status']:12s} "
            f"class={rec['class_desc_status']:12s} applicant={rec['applicant_name_status']:12s} warning={w.assessment}",
            flush=True,
        )
    pool.shutdown()
    return results, {"engine": pool.info(), "workers": workers}


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "n/a"


def summarize(results: list[Record], meta: Record, window: str) -> str:
    out = [
        "# Evaluation on real approved COLAs",
        "",
        f"_Generated by `tools/evaluate_real.py` on {len(results)} approved label applications fetched from TTB's "
        f"Public COLA Registry by `tools/cola_fetch.py` ({window}). The images and per-record results stay local "
        "(the artwork belongs to the brand owners); this file holds aggregate numbers only._",
        "",
        f"_Engine: {meta['engine'].get('engine', '?')}; alphabet: {meta['engine'].get('alphabet', 'full')}; workers: {meta['workers']}._",
        "",
        "## Read this first",
        "",
        "- The registry stores the applicant's uploads, usually flat artwork, often downscaled by the registry "
        "(see the image size row). This is the artwork tier of the real world, not the phone-photo tier.",
        "- The COLA form has no alcohol content or net contents fields, so for those only the read rate is reported.",
        '- Class/type is the registry\'s code description ("STRAIGHT BOURBON WHISKY", "TABLE RED WINE"), not the '
        'label\'s wording ("Kentucky Straight Bourbon Whiskey", "Cabernet Sauvignon"), so the class row understates '
        "what the tool would do with the application's actual wording. In the product a class/type that does not "
        "match is a review item with the closest text, never an issue (D-041); this row reports the raw text match.",
        '- The applicant is the permit holder; a label may lawfully name a different bottler ("bottled for"), '
        "so the applicant row also understates.",
        "- There is no ground truth for the warning statement beyond TTB's approval; the exact rate is what the "
        "comparator reports on the registry's image, and the hand-checked cases are listed at the end.",
        '- "Statement located" means the heading was found and a span accumulated behind it, at any similarity; '
        "the exact / slips / wording split below it is the accuracy, not the located rate.",
        '- "Country of origin found" is a proxy: the registry\'s country name matched somewhere on the label at '
        "partial-ratio 90 or better, without checking that it sits in an origin statement.",
        "- The alcohol and net-contents read rates count a parse anywhere in the concatenated text of all the "
        "record's images, as the extract-only mode of the product does.",
        "- Latency is the service call for the record (decode, all reads, the extra round when it runs); the file "
        "read and the pre-fit to the pixel cap are outside it. p95 is the nearest-rank percentile.",
        "- The applicant row runs the product's own bottler check on the registry's full item 8 line (names, "
        "address, the name used on the label), exactly as a spreadsheet would carry it (D-041).",
        "- Images above the product's 25 megapixel limit are shrunk to fit before the run; the deployed service "
        "refuses them with a message instead.",
        "",
    ]
    groups: dict[str, list[Record]] = defaultdict(list)
    for r in results:
        groups[r["beverage_type"]].append(r)
    groups["all"] = results

    def row(label: str, fn: Callable[[list[Record]], str]) -> str:
        return (
            "| "
            + label
            + " | "
            + " | ".join(fn(groups[k]) for k in ("spirits", "wine", "malt", "all") if k in groups)
            + " |"
        )

    heads = [k for k in ("spirits", "wine", "malt", "all") if k in groups]
    out += ["| | " + " | ".join(f"{k} (n={len(groups[k])})" for k in heads) + " |", "|---|" + "---:|" * len(heads)]

    def rate(field: str, statuses: tuple[str, ...]) -> Callable[[list[Record]], str]:
        return lambda g: pct(sum(r[f"{field}_status"] in statuses for r in g), len(g))

    for field, label in (
        ("brand", "Brand name"),
        ("class_desc", "Class/type (registry description)"),
        ("applicant_name", "Applicant name"),
    ):
        out.append(row(f"{label}: match", rate(field, ("match",))))
        out.append(row(f"{label}: match or needs review", rate(field, ("match", "needs_review"))))
    out.append(
        row(
            "Country of origin found (imports only)",
            lambda g: pct(sum(bool(r["origin_found"]) for r in g), sum(r["origin_found"] is not None for r in g)),
        )
    )
    out.append(
        row("Warning statement located (heading found)", lambda g: pct(sum(r["warning_present"] for r in g), len(g)))
    )
    out.append(row("Warning exact (of all)", lambda g: pct(sum(r["warning_assessment"] == "exact" for r in g), len(g))))
    out.append(
        row(
            "Warning exact (of located)",
            lambda g: pct(sum(r["warning_assessment"] == "exact" for r in g), sum(r["warning_present"] for r in g)),
        )
    )
    out.append(
        row(
            "Warning heading all capitals (of located)",
            lambda g: pct(sum(r["warning_anchor_caps"] == "match" for r in g), sum(r["warning_present"] for r in g)),
        )
    )
    out.append(row("Alcohol statement read", lambda g: pct(sum(r["alcohol_read"] for r in g), len(g))))
    out.append(row("Net contents read", lambda g: pct(sum(r["net_read"] for r in g), len(g))))
    out.append(row("All images readable", lambda g: pct(sum(r["readable"] for r in g), len(g))))
    out.append(row("Images per record, median", lambda g: f"{statistics.median(r['images'] for r in g):g}"))
    out.append(row("Longest image side, median px", lambda g: f"{statistics.median(r['long_side_px'] for r in g):.0f}"))
    out.append(row("Latency per record, median", lambda g: f"{statistics.median(r['ms'] for r in g):.0f} ms"))
    out.append(
        row(
            "Latency per record, p95",
            lambda g: f"{sorted(r['ms'] for r in g)[max(0, math.ceil(0.95 * len(g)) - 1)]} ms",  # nearest rank
        )
    )
    out.append("")
    out += ["## Warning assessment, all records", ""]
    c = Counter(r["warning_assessment"] for r in results)
    out += ["| assessment | records |", "|---|---:|"] + [
        f"| {k} | {v} |" for k, v in sorted(c.items(), key=lambda kv: -kv[1])
    ]
    out += ["", "## Hand-checked cases", ""]
    hand = Path("docs/EVAL_REAL_HANDCHECK.md")
    if hand.exists():  # written by a person after looking at the images; kept out of the generated part
        out.append(hand.read_text(encoding="utf-8").strip())
    else:
        out.append("_Not yet: the cases to look at are listed in results.csv (local)._")
    return "\n".join(out) + "\n\n" + f"_Regenerated {time.strftime('%Y-%m-%d %H:%M')}._\n"


_BOOL = {"True": True, "False": False, "": None}


def _load_results(real: Path) -> tuple[list[Record], Record]:
    """Re-read a previous run (results.csv + results_meta.json) so the report can be regenerated
    without another OCR pass, e.g. after the hand-checked section was written."""
    with (real / "results.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    results: list[Record] = []
    for r in rows:
        rec: Record = dict(r)
        for k in ("images", "long_side_px", "lines", "ms"):
            rec[k] = int(r[k])
        for k in ("readable", "rotated", "warning_present", "alcohol_read", "net_read"):
            rec[k] = _BOOL.get(r[k], False)
        rec["origin_found"] = _BOOL.get(r["origin_found"])
        results.append(rec)
    meta_path = real / "results_meta.json"
    meta: Record = (
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"engine": {}, "workers": "?"}
    )
    return results, meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default="tests/fixtures/real")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default="docs/EVAL_REAL.md")
    ap.add_argument("--window", default="records completed in the window given to cola_fetch.py")
    ap.add_argument("--summarize-only", action="store_true", help="rebuild the report from the last run's results.csv")
    args = ap.parse_args()
    real = Path(args.real)
    if args.summarize_only:
        results, meta = _load_results(real)
    else:
        results, meta = asyncio.run(run(real, args.workers))
        if not results:
            print("no records with images found", file=sys.stderr)
            sys.exit(1)
        with (real / "results.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
        (real / "results_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    Path(args.out).write_text(summarize(results, meta, args.window), encoding="utf-8")
    print(f"wrote {args.out} from {len(results)} records")


if __name__ == "__main__":
    main()
