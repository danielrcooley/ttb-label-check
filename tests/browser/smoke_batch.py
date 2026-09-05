"""Headless browser smoke test of the batch screen.

Loads the five-application demo batch, waits for completion, checks the summary and rows, opens a
detail panel (crops, highlights), records a decision, exports the CSV, and applies a filter.
Needs a running server and Playwright with Chromium.

    LABEL_CHECK_URL=http://127.0.0.1:8000 python tests/browser/smoke_batch.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("LABEL_CHECK_URL", "http://127.0.0.1:8000")
OUT = os.environ.get("LABEL_CHECK_SHOTS", ".")


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
    wait_ready()
    problems: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        page.on(
            "console",
            lambda m: problems.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None,
        )
        page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: problems.append(f"requestfailed: {r.url} {r.failure}"))
        page.on("response", lambda r: problems.append(f"http {r.status}: {r.url}") if r.status >= 400 else None)
        page.on("dialog", lambda d: d.accept() if d.type == "confirm" else d.dismiss())  # Start over asks first
        page.goto(BASE + "/#batch", wait_until="networkidle")
        page.wait_for_selector("#view-batch:not([hidden])")
        page.click("#batch-demo")
        page.wait_for_selector("#batch-status.is-busy", timeout=30000)
        page.wait_for_selector("#batch-status:not(.is-busy)", timeout=300000)
        print("status:", page.inner_text("#batch-status"))
        print("progress:", page.inner_text("#batch-progress .progress__text"))
        tiles = page.locator(".summary-tile").all_inner_texts()
        print("summary:", " | ".join(t.replace("\n", " ") for t in tiles))
        rows = page.locator(".batch-table > tbody > tr:not(.detail-row)")
        print("rows:", rows.count())
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td").all_inner_texts()
            print("   ", " | ".join(c.replace("\n", " / ")[:70] for c in cells[:4]))
        page.screenshot(path=f"{OUT}/ui_batch.png", full_page=True)

        page.locator(".batch-table button:has-text('Details')").first.click()
        page.wait_for_selector(".detail-panel .checklist", timeout=30000)
        print(
            "detail crops:",
            page.locator(".detail-panel img.crop").count(),
            "polygons:",
            page.locator(".detail-panel .overlay polygon").count(),
        )
        page.locator(".batch-table .decision-btns button:has-text('Approve')").first.click()
        if "decision recorded, Approve" not in page.inner_text("#batch-live"):
            problems.append("batch: the decision was not announced to assistive technology")
        if page.evaluate("document.activeElement?.dataset?.decision") != "approve":
            problems.append("batch: focus left the decision button after the table was rebuilt")
        with page.expect_download() as dl:
            page.click("#batch-export")
        with open(dl.value.path(), encoding="utf-8-sig") as f:
            text = f.read()
        lines = text.splitlines()
        print("export lines:", len(lines) - 1, "| header:", lines[0][:80])
        print("export row 1:", lines[1][:160])
        page.click("[data-filter=attention]")
        print("attention rows:", page.locator(".batch-table > tbody > tr:not(.detail-row)").count())
        if (
            page.get_attribute("[data-filter=attention]", "aria-pressed") != "true"
            or page.get_attribute("[data-filter=all]", "aria-pressed") != "false"
        ):
            problems.append("batch: filter buttons do not expose their pressed state")

        # Start over clears the images, the spreadsheet and the results
        page.click("#batch-reset")
        for _ in range(20):
            if "Cleared" in page.inner_text("#batch-status"):
                break
            page.wait_for_timeout(200)
        if (
            not page.is_hidden("#batch-results")
            or page.inner_text("#batch-image-count").strip()
            or page.inner_text("#batch-csv-summary").strip()
            or not page.is_disabled("#batch-start")
            or not page.is_hidden("#batch-reset")
        ):
            problems.append("batch: Start over left something behind")
        print("batch: Start over clears images, spreadsheet and results")
        browser.close()

    print("\nPROBLEMS:" if problems else "\nno problems detected")
    for x in problems[:30]:
        print(" -", x[:300])
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
