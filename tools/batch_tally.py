"""Run a folder of real label images and their spreadsheet through the deployed batch screen, export
the CSV, and tally what the tool said: verdicts, per-check statuses, and errors. This reproduces the
README's "real applications through the batch screen" row.

The corpus is TTB's Public COLA Registry sample fetched by tools/cola_fetch.py (git-ignored, the
artwork is not ours to redistribute). The spreadsheet is built from the registry's own fields:
names and address as registered, the class code description, the origin; no alcohol content or net
contents, because the COLA form carries neither.

    python tools/batch_tally.py --url https://labelcheck.dev --real tests/fixtures/real
    python tools/batch_tally.py --url http://127.0.0.1:8000 --real tests/fixtures/real --limit 20

Needs Playwright with Chromium (pip install playwright && playwright install chromium).
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path


def build_applications(real: Path, limit: int | None) -> tuple[Path, list[str]]:
    """The batch spreadsheet from cola.csv, and the image paths it names."""
    rows = list(csv.DictReader((real / "cola.csv").open(encoding="utf-8")))
    if limit:
        rows = rows[:limit]
    head = [
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
    body: list[list[str]] = []
    images: list[str] = []
    for row in rows:
        names = [n.strip() for n in row["images"].split(";") if n.strip() and (real / n.strip()).exists()]
        if not names:
            continue
        images += [str(real / n) for n in names]
        imported = row["domestic"] == "no"
        body.append(
            [
                row["ttbid"],
                row["beverage_type"],
                row["brand"],
                row["class_desc"],
                "",
                "",
                row["applicant"],
                row["origin_desc"] if imported else "USA",
                "yes" if imported else "no",
                ";".join(names),
            ]
        )
    fd, name = tempfile.mkstemp(suffix=".csv")
    with open(fd, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(head)
        writer.writerows(body)
    return Path(name), images


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://labelcheck.dev")
    ap.add_argument("--real", default="tests/fixtures/real")
    ap.add_argument("--limit", type=int, default=None, help="first N records only")
    ap.add_argument("--export", default=None, help="where to keep the exported CSV")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    real = Path(args.real)
    sheet, images = build_applications(real, args.limit)
    print(f"{len(images)} images, spreadsheet {sheet}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.goto(args.url + "/#batch")
        page.wait_for_selector("#view-batch:not([hidden])", timeout=15000)
        page.set_input_files("#batch-files", images)
        page.set_input_files("#batch-csv", str(sheet))
        page.wait_for_function(
            "document.querySelector('#batch-csv-summary p')?.textContent.includes('row')", timeout=60000
        )
        print("spreadsheet:", page.inner_text("#batch-csv-summary p"))
        t0 = time.time()
        page.click("#batch-start")
        page.wait_for_selector("#batch-status.is-busy", timeout=30000)
        page.wait_for_selector("#batch-status:not(.is-busy)", timeout=3_600_000)
        print("status:", page.inner_text("#batch-status"), f"({time.time() - t0:.0f} s)")
        print("summary:", page.inner_text("#batch-summary").replace("\n", " | "))
        with page.expect_download() as dl:
            page.click("#batch-export")
        path = Path(args.export) if args.export else Path(tempfile.gettempdir()) / "label-check-batch-tally.csv"
        dl.value.save_as(str(path))
        browser.close()
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    print("exported rows:", len(rows))
    print("verdicts:", dict(Counter(r.get("verdict") for r in rows)))
    for col in [c for c in rows[0] if c.endswith("_status")] + ["warning_present", "warning_exact"]:
        print(f"{col:28s}", dict(Counter(r[col] for r in rows)))
    errors = [r for r in rows if r.get("verdict") in ("", "error")]
    for r in errors[:10]:
        print("ERROR:", r.get("application_id"), r.get("summary"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
