# Browser smoke tests

Headless Chromium checks of the real interface: console errors, CSP violations, failed requests,
the three one-click samples, the demo batch (pairing, details, decisions, export, filters), and
a phone-sized viewport with no horizontal scrolling.

They need a running server and Playwright with Chromium, so they are not part of CI:

```bash
pip install playwright && playwright install chromium
uvicorn app.main:app --port 8000 &
LABEL_CHECK_URL=http://127.0.0.1:8000 python tests/browser/smoke_single.py
LABEL_CHECK_URL=http://127.0.0.1:8000 python tests/browser/smoke_batch.py
```

Screenshots are written to the current directory (or `LABEL_CHECK_SHOTS`).
