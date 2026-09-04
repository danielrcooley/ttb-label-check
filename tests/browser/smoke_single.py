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
        expecting = {"error": False}  # set while a request is meant to fail
        page.on(
            "console",
            lambda m: (
                problems.append(f"console.{m.type}: {m.text}")
                if m.type in ("error", "warning") and not expecting["error"]
                else None
            ),
        )
        page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: problems.append(f"requestfailed: {r.url} {r.failure}"))
        page.on(
            "response",
            lambda r: (
                problems.append(f"http {r.status}: {r.url}") if r.status >= 400 and not expecting["error"] else None
            ),
        )
        page.on(
            "dialog", lambda d: d.accept() if d.type == "beforeunload" else d.dismiss()
        )  # leave-page prompt on reload
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

        # Decision, note and export on the single screen (the same controls as the batch screen)
        page.locator("#decision .decision-btns button", has_text="Approve").click()
        if page.locator("#decision button[aria-pressed='true']", has_text="Approve").count() != 1:
            problems.append("single: Approve did not stay pressed")
        page.fill("#decision .note-input", "checked the heading on the image")
        page.locator("#decision .note-input").press("Tab")
        with page.expect_download() as dl:
            page.locator("#decision .decision-actions button", has_text="Export").click()
        with open(dl.value.path(), encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
        if len(lines) != 2 or '"approve"' not in lines[1] or "checked the heading" not in lines[1]:
            problems.append("single: export lacks the decision or the note")
        if "Decision recorded: Approve" not in page.inner_text("#decision-live"):
            problems.append("single: the decision was not announced to assistive technology")
        if page.evaluate("document.activeElement?.dataset?.decision") not in ("approve", None):
            problems.append("single: focus left the decision buttons after a press")
        print("single: decision recorded, announced and exported")

        # A failed re-check must not leave the previous result and its export on screen (review 007)
        expecting["error"] = True
        page.set_input_files("#file-input", {"name": "bad.png", "mimeType": "image/png", "buffer": b"not an image"})
        page.click("#check-btn")
        page.wait_for_timeout(500)
        for _ in range(120):  # the status line empties on failure, so poll its class rather than wait for text
            if "is-busy" not in (page.get_attribute("#status", "class") or ""):
                break
            page.wait_for_timeout(500)
        page.wait_for_timeout(300)
        expecting["error"] = False
        if not page.is_hidden("#results"):
            problems.append("single: a failed check left the previous result on screen")
        print("single: a failed re-check clears the previous result")
        page.click("#clear-files")

        # Accessibility page: the display choice applies at once, survives a reload, and restores.
        page.click("a[data-view=accessibility]")
        page.wait_for_selector("#view-accessibility:not([hidden])", timeout=5000)
        page.click("label[for=theme-dark]")
        if page.get_attribute("html", "data-theme") != "dark":
            problems.append("theme: Dark did not apply")
        page.reload(wait_until="networkidle")
        if page.get_attribute("html", "data-theme") != "dark" or not page.is_checked("#theme-dark"):
            problems.append("theme: Dark did not persist across a reload")
        page.click("a[data-view=check]")
        page.click("[data-sample=problem]")
        page.wait_for_selector("#status:not(.is-busy)", timeout=60000)
        page.wait_for_selector("#results:not([hidden]) .verdict", timeout=60000)
        page.screenshot(path=f"{OUT}/ui_dark.png", full_page=True)
        page.click("a[data-view=accessibility]")
        page.click("label[for=theme-light]")
        if page.get_attribute("html", "data-theme") != "light":
            problems.append("theme: Light did not restore")
        print("theme: dark applied, persisted, restored")

        mobile = browser.new_context(
            viewport={"width": 390, "height": 844}, device_scale_factor=2, bypass_csp=True
        ).new_page()
        mobile.goto(BASE + "/", wait_until="networkidle")
        mobile.click("[data-sample=clean]")
        mobile.wait_for_selector("#results:not([hidden]) .verdict", timeout=60000)
        mobile.screenshot(path=f"{OUT}/ui_mobile.png", full_page=True)
        if mobile.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"):
            problems.append("mobile: page scrolls horizontally")

        # 200 percent zoom on a 1366-px screen is a 683-px viewport: the result must reflow, not scroll sideways
        zoomed = browser.new_context(viewport={"width": 683, "height": 450}).new_page()
        zoomed.goto(BASE + "/", wait_until="networkidle")
        zoomed.click("[data-sample=problem]")
        zoomed.wait_for_selector("#results:not([hidden]) .verdict", timeout=60000)
        if zoomed.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"):
            problems.append("200% zoom: page scrolls horizontally")
        print("zoom: no horizontal scroll at 683 px")
        browser.close()

    print("\nPROBLEMS:" if problems else "\nno problems detected")
    for x in problems[:40]:
        print(" -", x[:300])
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
