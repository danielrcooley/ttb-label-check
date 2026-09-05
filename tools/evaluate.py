#!/usr/bin/env python
"""Accuracy and latency evaluation on the synthetic corpus, through the real pipeline.

Tiers (from tests/fixtures/labels/manifest.json):
  artwork   clean front + clean back for every application
  degraded  each degraded image paired with its clean sibling (rotate, blur, glare, low contrast,
            perspective, small, jpeg, sideways)
  problem   labels with a planted defect; we check the defect is reported

Reports per-field match rate on the artwork tier (recall), the false-alarm rate (checks on
clean artwork that did not come back as Match), degraded-tier match rate, problem detection,
and per-application latency. Writes docs/EVAL.md and docs/eval.json.

Usage:
    python tools/evaluate.py [--labels tests/fixtures/labels] [--workers 2] [--out docs/EVAL.md]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.ocr.pool import OcrPool
from app.ocr.rapid import RapidEngine
from app.schemas import ApplicationFields
from app.services import Upload, verify

FIELDS = ["brand_name", "class_type", "alcohol_content", "net_contents", "bottler", "country_of_origin"]
DEGRADATIONS = {"rotate7", "blur", "glare", "lowcontrast", "perspective", "small", "jpeg", "rotate90"}
PROBLEM_EXPECTATIONS = {
    "wrong_abv": lambda r: any(c.id == "alcohol_content" and c.status == "mismatch" for c in r.checks),
    "titlecase": lambda r: r.warning.present and r.warning.anchor_caps == "needs_review",
    "altered": lambda r: r.warning.present and not r.warning.exact and r.verdict == "issues_found",
    "missing": lambda r: not r.warning.present and r.verdict == "issues_found",
    "tiny": None,  # planted defect the tool does not assess (physical type size)
    "allbold": lambda r: r.warning.present and r.warning.anchor_bold == "needs_review",
}


def app_fields(app: dict) -> ApplicationFields:
    return ApplicationFields(
        application_id=app["id"],
        beverage_type=app["beverage_type"],
        brand_name=app["brand"],
        class_type=app["class_type"],
        alcohol_content=app["alcohol_content"],
        net_contents=app["net_contents"],
        bottler=app["bottler"],
        country_of_origin=app["origin"].replace("Product of ", ""),
        imported="USA" not in app["origin"],
    )


async def run(labels: Path, workers: int) -> dict:
    settings = Settings(ocr_workers=workers)
    pool = OcrPool(settings, lambda: RapidEngine(settings))
    pool.warmup()
    manifest = json.loads((labels / "manifest.json").read_text(encoding="utf-8"))

    def upload(name: str) -> Upload:
        return Upload(data=(labels / name).read_bytes(), filename=name)

    tiers: dict[str, list[dict]] = defaultdict(list)
    for app in manifest["applications"]:
        imgs = {im["variant"] + ":" + im["side"]: im["file"] for im in app["images"]}
        front, back = imgs.get("clean:front"), imgs.get("clean:back")
        fields = app_fields(app)
        cases = [("artwork", "clean", [front, back])]
        for im in app["images"]:
            v = im["variant"]
            if v in DEGRADATIONS:
                pair = [im["file"], back] if im["side"] == "front" else [front, im["file"]]
                cases.append(("degraded", v, pair))
            elif v in PROBLEM_EXPECTATIONS:
                pair = [im["file"], back] if im["side"] == "front" else [front, im["file"]]
                cases.append(("problem", v, pair))
        for tier, variant, files in cases:
            t0 = time.perf_counter()
            res = await verify(fields, [upload(f) for f in files], settings, pool, interactive=True)
            ms = int((time.perf_counter() - t0) * 1000)
            tiers[tier].append(
                {
                    "app": app["id"],
                    "variant": variant,
                    "files": files,
                    "ms": ms,
                    "verdict": res.verdict,
                    "checks": {c.id: c.status for c in res.checks},
                    "warning_exact": res.warning.exact,
                    "warning_present": res.warning.present,
                    "type_weight": str(res.warning.anchor_bold),  # match / needs_review / not_checked (D-045)
                    "type_weight_basis": res.warning.type_weight_basis or "",
                    "type_weight_ratio": res.warning.type_weight_ratio,
                    "detected": (PROBLEM_EXPECTATIONS[variant](res) if PROBLEM_EXPECTATIONS.get(variant) else None)
                    if tier == "problem"
                    else None,
                    "assessed": tier == "problem" and PROBLEM_EXPECTATIONS.get(variant) is not None,
                }
            )
    pool.shutdown()
    return {"tiers": tiers, "engine": pool.info(), "workers": workers}


def _type_weight_line(cases: list[dict]) -> str:
    """One line of counts for the bold-type measurement (D-045): what it found and where it abstained."""
    st = Counter(c.get("type_weight", "") for c in cases if c["warning_present"])
    basis = Counter(c.get("type_weight_basis", "") for c in cases if c["warning_present"])
    measured_unsure = sum(
        1
        for c in cases
        if c["warning_present"] and c.get("type_weight") == "not_checked" and c.get("type_weight_ratio") is not None
    )
    unmeasured = st.get("not_checked", 0) - measured_unsure
    reasons = ", ".join(
        f"{k} {v}" for k, v in sorted(basis.items()) if k in ("too small", "size differs", "no heading line")
    )
    return (
        f"- Warning type weight of the statements located: heading heavier {st.get('match', 0)}, "
        f"same weight (Needs review) {st.get('needs_review', 0)}, measured but inconclusive {measured_unsure}, "
        f"not measured {unmeasured}" + (f" ({reasons})" if reasons else "")
    )


def summarize(data: dict) -> tuple[str, dict]:
    out: list[str] = [
        "# Evaluation",
        "",
        "_Generated by `tools/evaluate.py` on the committed synthetic corpus (10 fictional "
        "applications; front + back per case). Numbers are from the real pipeline on the machine "
        "that ran it; deployed numbers are in the README._",
        "",
        "_Engine: {engine}; alphabet: {alphabet}; det {det}; rec {rec}; workers: {workers}._".format(
            engine=data.get("engine", {}).get("engine", "?"),
            alphabet=data.get("engine", {}).get("alphabet", "full"),
            det=data.get("engine", {}).get("det", "?"),
            rec=data.get("engine", {}).get("rec", "?"),
            workers=data.get("workers", "?"),
        ),
        "",
    ]
    summary: dict = {}
    for tier in ("artwork", "degraded", "problem"):
        cases = data["tiers"].get(tier, [])
        if not cases:
            continue
        lat = [c["ms"] for c in cases]
        summary[tier] = {
            "cases": len(cases),
            "p50_ms": statistics.median(lat),
            "p95_ms": sorted(lat)[max(0, math.ceil(0.95 * len(lat)) - 1)],  # nearest rank
        }
        out += [
            f"## {tier.capitalize()} tier ({len(cases)} cases)",
            "",
            f"- Per-application latency (two images, parallel): median {summary[tier]['p50_ms']:.0f} ms, "
            f"p95 {summary[tier]['p95_ms']:.0f} ms",
            "",
        ]
        if tier in ("artwork", "degraded"):
            out += ["| Field | Match | Needs review | Mismatch / not found | Match rate |", "|---|---:|---:|---:|---:|"]
            rates = {}
            for f in FIELDS:
                cnt = Counter(c["checks"].get(f, "absent") for c in cases)
                n = sum(v for k, v in cnt.items() if k != "absent")
                match = cnt.get("match", 0)
                rates[f] = match / n if n else None
                out.append(
                    f"| {f} | {match} | {cnt.get('needs_review', 0)} | {cnt.get('mismatch', 0) + cnt.get('not_found', 0)} | "
                    f"{100 * match / n:.0f}% |"
                    if n
                    else f"| {f} | - | - | - | - |"
                )
            wex = sum(1 for c in cases if c["warning_exact"])
            out.append(
                f"| warning exact | {wex} | {sum(1 for c in cases if c['warning_present'] and not c['warning_exact'])} | "
                f"{sum(1 for c in cases if not c['warning_present'])} | {100 * wex / len(cases):.0f}% |"
            )
            verdicts = Counter(c["verdict"] for c in cases)
            out += ["", f"- Verdicts: {dict(verdicts)}", _type_weight_line(cases)]
            if tier == "artwork":
                total_checks = sum(1 for c in cases for f in FIELDS if f in c["checks"])
                non_match = sum(1 for c in cases for f in FIELDS if f in c["checks"] and c["checks"][f] != "match")
                summary["false_alarm_rate"] = non_match / total_checks if total_checks else 0
                out.append(
                    f"- **False-alarm rate on clean artwork: {100 * summary['false_alarm_rate']:.1f}%** "
                    f"({non_match} of {total_checks} field checks not reported as Match)"
                )
            summary[tier]["rates"] = rates
            out.append("")
            if tier == "degraded":
                out += ["| Degradation | cases | verdicts | median ms |", "|---|---:|---|---:|"]
                by = defaultdict(list)
                for c in cases:
                    by[c["variant"]].append(c)
                for v, cs in sorted(by.items()):
                    out.append(
                        f"| {v} | {len(cs)} | {dict(Counter(x['verdict'] for x in cs))} | {statistics.median(x['ms'] for x in cs):.0f} |"
                    )
                out.append("")
        else:
            out += ["| Planted defect | detected | note |", "|---|---|---|"]
            notes = {
                "tiny": "NOT ASSESSED by design: physical type size",
            }
            det = 0
            assessed = [c for c in cases if c["assessed"]]
            for c in cases:
                det += bool(c["detected"])
                mark = ("yes" if c["detected"] else "NO") if c["assessed"] else "n/a"
                out.append(f"| {c['variant']} ({c['app']}) | {mark} | {notes.get(c['variant'], '')} |")
            summary["problem_detection"] = det / len(assessed) if assessed else None
            out += [
                "",
                f"- Detection rate over the defects the tool assesses: {det}/{len(assessed)}; "
                f"{len(cases) - len(assessed)} planted defect{'' if len(cases) - len(assessed) == 1 else 's'} "
                f"{'is' if len(cases) - len(assessed) == 1 else 'are'} outside this build's checks and listed as n/a",
                _type_weight_line(cases),
                "",
            ]
    return "\n".join(out), summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="tests/fixtures/labels")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default="docs/EVAL.md")
    args = ap.parse_args()
    data = asyncio.run(run(Path(args.labels), args.workers))
    md, summary = summarize(data)
    Path(args.out).write_text(md, encoding="utf-8")
    Path(args.out).with_name("eval.json").write_text(
        json.dumps({"summary": summary, **data}, indent=1, default=str), encoding="utf-8"
    )
    print(md)


if __name__ == "__main__":
    main()
