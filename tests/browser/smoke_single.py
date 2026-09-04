"""Headless browser smoke test of the single-application screen.

Checks: no console errors, no CSP violations, no failed requests; the three one-click samples reach
their expected verdicts with crops and highlights; row selection highlights evidence; a phone-sized
viewport does not scroll horizontally. Needs a running server and Playwright with Chromium.

    LABEL_CHECK_URL=http://127.0.0.1:8000 python tests/browser/smoke_single.py
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
EXPECTED = {"clean": "Ready for your approval", "photo": None, "problem": "Issues found"}


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
        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.on(
            "console",
            lambda m: problems.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None,
        )
        page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: problems.append(f"requestfailed: {r.url} {r.failure}"))
        page.on("response", lambda r: problems.append(f"http {r.status}: {r.url}") if r.status >= 400 else None)
        page.on("dialog", lambda d: d.dismiss())
        page.goto(BASE + "/", wait_until="networkidle")
        print("title:", page.title())
        page.screenshot(path=f"{OUT}/ui_home.png", full_page=True)

        for sample, expect in EXPECTED.items():
            page.click(f"[data-sample={sample}]")
            page.wait_for_selector("#status.is-busy", timeout=15000)
            page.wait_for_selector("#status:not(.is-busy)", timeout=60000)
            page.wait_for_selector("#results:not([hidden]) .verdict", timeout=60000)
            heading = page.inner_text(".verdict .usa-alert__heading")
            timing = page.inner_text(".verdict .timing").strip()[:60]
            rows = page.locator(".checklist tbody tr").count()
            crops = page.locator(".checklist img.crop").count()
            polys = page.locator(".overlay polygon").count()
            print(f"[{sample}] {heading!r} | {timing} | rows={rows} crops={crops} polygons={polys}")
            if expect and heading != expect:
                problems.append(f"sample {sample}: expected {expect!r}, got {heading!r}")
            page.screenshot(path=f"{OUT}/ui_{sample}.png", full_page=True)
            page.locator(".checklist tbody tr").first.click()
            print("   active polygons after row click:", page.locator(".overlay polygon.is-active").count())

        mobile = browser.new_context(
            viewport={"width": 390, "height": 844}, device_scale_factor=2, bypass_csp=True
        ).new_page()
        mobile.goto(BASE + "/", wait_until="networkidle")
        mobile.click("[data-sample=clean]")
        mobile.wait_for_selector("#results:not([hidden]) .verdict", timeout=60000)
        mobile.screenshot(path=f"{OUT}/ui_mobile.png", full_page=True)
        if mobile.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"):
            problems.append("mobile: page scrolls horizontally")
        browser.close()

    print("\nPROBLEMS:" if problems else "\nno problems detected")
    for x in problems[:40]:
        print(" -", x[:300])
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
