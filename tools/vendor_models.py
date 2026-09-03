#!/usr/bin/env python
"""Vendor the OCR model files into the repository and record their SHA-256.

The application must never download models at build or run time (restricted networks,
reproducible builds). This tool copies the chosen models out of the installed `rapidocr`
package (which downloads and hash-verifies them once, on the developer's machine) into
`app/models/` and writes `app/models/MANIFEST.json`. The app loads models only from there.

Usage:
    python tools/vendor_models.py --det PP-OCRv6_det_small.onnx --rec PP-OCRv6_rec_small.onnx \
        --cls ch_ppocr_mobile_v2.0_cls_mobile.onnx
    python tools/vendor_models.py --verify        # recompute hashes and compare to MANIFEST.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "app" / "models"
MANIFEST = DEST / "MANIFEST.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def package_models_dir() -> Path:
    import rapidocr

    return Path(rapidocr.__file__).resolve().parent / "models"


def vendor(names: dict[str, str | None]) -> None:

    src_dir = package_models_dir()
    DEST.mkdir(parents=True, exist_ok=True)
    entries = {}
    for role, name in names.items():
        if not name:
            continue
        src = src_dir / name
        if not src.exists():
            sys.exit(
                f"{src} not found. Instantiate RapidOCR once with that model so the package "
                f"downloads and verifies it, then re-run."
            )
        dst = DEST / name
        shutil.copyfile(src, dst)
        entries[role] = {"file": name, "sha256": sha256(dst), "bytes": dst.stat().st_size}
        print(f"{role}: {name} {entries[role]['bytes']:,} bytes sha256={entries[role]['sha256'][:16]}...")
    from importlib.metadata import version

    manifest = {
        "vendored_on": date.today().isoformat(),
        "source_package": f"rapidocr {version('rapidocr')}",
        "upstream": "RapidAI/RapidOCR (Apache-2.0); models derived from PaddleOCR (Apache-2.0)",
        "models": entries,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {MANIFEST}")


def verify() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bad = 0
    for role, m in manifest["models"].items():
        p = DEST / m["file"]
        ok = p.exists() and sha256(p) == m["sha256"]
        print(f"{role}: {m['file']} {'OK' if ok else 'MISMATCH'}")
        bad += 0 if ok else 1
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--det")
    ap.add_argument("--rec")
    ap.add_argument("--cls")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        sys.exit(verify())
    if not (args.det and args.rec):
        sys.exit("--det and --rec are required (or --verify)")
    vendor({"det": args.det, "rec": args.rec, "cls": args.cls})


if __name__ == "__main__":
    main()
