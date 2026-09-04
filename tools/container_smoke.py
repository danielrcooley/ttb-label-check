"""Smoke test run INSIDE the container by CI (stdlib only, no network beyond localhost).

Waits for readiness, then verifies the bundled clean sample through the real API and asserts the
verdict. Exits non-zero on any failure so CI cannot pass silently.
"""

import contextlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

PORT = os.environ.get("PORT", "8000")
BASE = f"http://127.0.0.1:{PORT}"
SAMPLES = "/app/app/static/samples"


def get(path: str, timeout: float = 5.0) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def wait_ready(seconds: int) -> float:
    t0 = time.time()
    last = None
    while time.time() - t0 < seconds:
        try:
            code, body = get("/api/v1/ready", timeout=3)
            last = (code, body)
            if code == 200:
                return time.time() - t0
        except Exception as exc:  # connection refused while uvicorn binds
            last = repr(exc)
        time.sleep(1)
    print("NOT READY after", seconds, "s; last:", last, file=sys.stderr)
    with contextlib.suppress(Exception):
        print(json.dumps(get("/api/v1/health")[1], indent=1), file=sys.stderr)
    sys.exit(2)


def verify_sample() -> dict:
    boundary = uuid.uuid4().hex
    app = {
        "beverage_type": "spirits",
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "bottler": "Distilled and Bottled by Old Tom Distillery, Bardstown, Kentucky",
        "country_of_origin": "USA",
    }
    body = b""
    body += f'--{boundary}\r\nContent-Disposition: form-data; name="application"\r\n\r\n'.encode()
    body += json.dumps(app).encode() + b"\r\n"
    for name in ("clean_front.png", "clean_back.png"):
        with open(f"{SAMPLES}/{name}", "rb") as f:
            data = f.read()
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="images"; filename="{name}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode()
        body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{BASE}/api/v1/verify", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


if __name__ == "__main__":
    warm = wait_ready(int(os.environ.get("READY_TIMEOUT", "180")))
    print(f"ready after {warm:.1f}s")
    t0 = time.time()
    res = verify_sample()
    print(f"verdict={res['verdict']} total_ms={res['timing']['total_ms']} wall_ms={int((time.time() - t0) * 1000)}")
    print(res["summary"])
    assert res["verdict"] == "ready_for_approval", res["summary"]
    assert res["warning"]["exact"], res["warning"]
    code, health = get("/api/v1/health")
    print("health:", code, {k: health[k] for k in ("ready", "max_concurrency", "git_sha")})
