"""Scale run of the batch screen: N applications (2 images each) through the real interface.

Builds a temporary folder of renamed fixture images plus a CSV, drives the browser through the
batch screen, and reports wall time, per-image latency percentiles as shown by the page, and the
summary tiles. Evidence for the "200 to 300 at once" requirement.

    LABEL_CHECK_URL=http://127.0.0.1:8000 python tests/browser/batch_scale.py --apps 150
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("LABEL_CHECK_URL", "http://127.0.0.1:8000")
ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "labels"
CSV_FIELDS = [
    "application_id",
    "beverage_type",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler",
    "country_of_origin",
    "imported",
    "images",
]


def build_corpus(n_apps: int, out: Path) -> Path:
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    apps = manifest["applications"]
    rows = []
    for i in range(n_apps):
        src = apps[i % len(apps)]
        app_id = f"COLA-{i + 1:04d}"
        imgs = {im["side"]: im["file"] for im in src["images"] if im["variant"] == "clean"}
        names = []
        for side in ("front", "back"):
            name = f"{app_id}_{side}.png"
            shutil.copyfile(FIXTURES / imgs[side], out / name)
            names.append(name)
        rows.append(
            {
                "application_id": app_id,
                "beverage_type": src["beverage_type"],
                "brand_name": src["brand"],
                "class_type": src["class_type"],
                "alcohol_content": src["alcohol_content"],
                "net_contents": src["net_contents"],
                "bottler": src["bottler"],
                "country_of_origin": src["origin"].replace("Product of ", ""),
                "imported": "yes" if "USA" not in src["origin"] else "no",
                "images": ";".join(names),
            }
        )
    csv_path = out / "applications.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return csv_path


def wait_ready(seconds: int = 120) -> None:
    for _ in range(seconds):
        try:
            with urllib.request.urlopen(f"{BASE}/api/v1/health", timeout=3) as r:
                if json.load(r).get("ready"):
                    return
        except Exception:
            pass
        time.sleep(1)
    sys.exit("server not ready")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apps", type=int, default=150)
    ap.add_argument("--report", default=str(ROOT / "docs" / "LOADTEST.md"))
    args = ap.parse_args()
    wait_ready()
    tmp = Path(tempfile.mkdtemp(prefix="label-check-scale-"))
    csv_path = build_corpus(args.apps, tmp)
    images = sorted(p for p in tmp.glob("*.png"))
    print(f"corpus: {args.apps} applications, {len(images)} images in {tmp}")
    problems: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={"width": 1366, "height": 900}).new_page()
        page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
        page.on("console", lambda m: problems.append(f"console.error: {m.text}") if m.type == "error" else None)
        page.on("dialog", lambda d: d.dismiss())
        page.goto(BASE + "/#batch", wait_until="networkidle")
        page.set_input_files("#batch-files", [str(x) for x in images])
        page.set_input_files("#batch-csv", str(csv_path))
        page.wait_for_selector("#batch-csv-summary p")
        print("intake:", page.inner_text("#batch-image-count"), "|", page.inner_text("#batch-csv-summary p"))
        t0 = time.time()
        page.click("#batch-start")
        page.wait_for_selector("#batch-status.is-busy", timeout=60000)
        page.wait_for_selector("#batch-status:not(.is-busy)", timeout=3600000)
        wall = time.time() - t0
        print("status:", page.inner_text("#batch-status"))
        tiles = page.locator(".summary-tile").all_inner_texts()
        print("summary:", " | ".join(t.replace("\n", " ") for t in tiles))
        ready = int(tiles[0].split()[0]) if tiles else -1
        block = "\n".join(
            [
                f"### browser batch: {args.apps} applications x 2 images through the batch screen, host {BASE}",
                f"- wall {wall:.0f} s ({args.apps * 2 / wall:.2f} images/s end to end, including compare calls and rendering)",
                f"- summary tiles: {' | '.join(t.replace(chr(10), ' ') for t in tiles)}",
                f"- {'no browser errors' if not problems else str(len(problems)) + ' browser problems: ' + problems[0][:200]}",
            ]
        )
        print(block)
        with open(args.report, "a", encoding="utf-8") as f:
            f.write(f"{block}\n- run at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        browser.close()
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if not problems and ready == args.apps else 1


if __name__ == "__main__":
    sys.exit(main())
