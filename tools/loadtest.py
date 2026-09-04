#!/usr/bin/env python
"""Black-box load test against a running instance (local or deployed).

Two modes:
  steady  N requests through a pool of C concurrent clients that honor 429 + Retry-After, the way
          the batch screen does. Reports throughput and latency percentiles.
  burst   Fire C requests at the same instant with no backoff, to show the 429 path: how many
          were served, how many refused, and that health kept answering.

Usage:
    python tools/loadtest.py --url http://127.0.0.1:8000 --mode steady --n 100 --concurrency 4
    python tools/loadtest.py --url https://<host> --mode burst --concurrency 32
    python tools/loadtest.py --url ... --mode steady --n 40 --endpoint verify   # front+back application
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "app" / "static" / "samples"
APPLICATION = {
    "application_id": "LOADTEST",
    "beverage_type": "spirits",
    "brand_name": "OLD TOM DISTILLERY",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45% Alc./Vol. (90 Proof)",
    "net_contents": "750 mL",
    "bottler": "Distilled and Bottled by Old Tom Distillery, Bardstown, Kentucky",
    "country_of_origin": "USA",
    "imported": False,
}


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * (len(s) - 1)))]


async def one(
    client: httpx.AsyncClient, url: str, endpoint: str, files: list[tuple[str, bytes]], batch: bool, retry: bool
) -> tuple[int, float, int, float | None]:
    """Returns (final status, wall ms including retries, number of 429s seen, server-side ms or None)."""
    headers = {"X-Batch": "1"} if batch else {}
    refused = 0
    t0 = time.perf_counter()
    for attempt in range(8):
        form = [("images", (n, b, "image/png")) for n, b in files]
        data = {"application": json.dumps(APPLICATION)} if endpoint == "verify" else None
        try:
            r = await client.post(f"{url}/api/v1/{endpoint}", files=form, data=data, headers=headers)
        except httpx.HTTPError:
            return 0, (time.perf_counter() - t0) * 1000, refused, None
        if r.status_code == 429 and retry:
            refused += 1
            base = float(r.headers.get("Retry-After", "1"))
            await asyncio.sleep(base * (attempt + 1) + random.random() * 0.5)  # grows like the browser client
            continue
        server_ms: float | None = None
        if r.status_code == 200:
            try:
                server_ms = float(r.json()["timing"]["total_ms"])  # the server's own clock, network excluded
            except (ValueError, KeyError, TypeError):
                server_ms = None
        return r.status_code, (time.perf_counter() - t0) * 1000, refused, server_ms
    return 429, (time.perf_counter() - t0) * 1000, refused, None


async def steady(args: argparse.Namespace, files: list[tuple[str, bytes]]) -> str:
    sem = asyncio.Semaphore(args.concurrency)
    results: list[tuple[int, float, int, float | None]] = []
    async with httpx.AsyncClient(timeout=60) as client:

        async def task() -> None:
            async with sem:
                results.append(
                    await one(client, args.url, args.endpoint, files, batch=not args.interactive, retry=True)
                )

        t0 = time.perf_counter()
        await asyncio.gather(*(task() for _ in range(args.n)))
        wall = time.perf_counter() - t0
    ok = [ms for st, ms, _, _ in results if st == 200]
    server = [sv for st, _, _, sv in results if st == 200 and sv is not None]
    codes: dict[int, int] = {}
    for st, _, _, _ in results:
        codes[st] = codes.get(st, 0) + 1
    refused = sum(r for _, _, r, _ in results)
    return "\n".join(
        [
            f"### steady{' interactive' if args.interactive else ''}: {args.n} x {args.endpoint} "
            f"({len(files)} image(s) each), concurrency {args.concurrency}, host {args.url}",
            f"- wall {wall:.1f} s, throughput {args.n / wall:.2f} req/s ({args.n * len(files) / wall:.2f} images/s)",
            f"- wall latency ms per successful request, including any backoff waits: p50 {pct(ok, 0.5):.0f}, "
            f"p95 {pct(ok, 0.95):.0f}, max {max(ok) if ok else 0:.0f}",
            f"- server-side latency ms (the response's own timing.total_ms, network excluded): p50 {pct(server, 0.5):.0f}, "
            f"p95 {pct(server, 0.95):.0f}, max {max(server) if server else 0:.0f}",
            f"- final status codes: {codes}; 429 responses absorbed by backoff along the way: {refused}",
        ]
    )


async def burst(args: argparse.Namespace, files: list[tuple[str, bytes]]) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        t0 = time.perf_counter()
        health_task = asyncio.create_task(client.get(f"{args.url}/api/v1/health"))
        results = await asyncio.gather(
            *(one(client, args.url, args.endpoint, files, batch=True, retry=False) for _ in range(args.concurrency))
        )
        wall = time.perf_counter() - t0
        h = await health_task
    codes: dict[int, int] = {}
    for st, _, _, _ in results:
        codes[st] = codes.get(st, 0) + 1
    served = [ms for st, ms, _, _ in results if st == 200]
    return "\n".join(
        [
            f"### burst: {args.concurrency} simultaneous {args.endpoint} requests, no backoff, host {args.url}",
            f"- status codes: {codes} (429 = refused immediately with Retry-After)",
            f"- served latency ms: p50 {pct(served, 0.5):.0f}, max {max(served) if served else 0:.0f}; wall {wall:.1f} s",
            f"- health during burst: HTTP {h.status_code}, in_flight={h.json().get('in_flight')}",
        ]
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--mode", choices=["steady", "burst"], default="steady")
    ap.add_argument("--endpoint", choices=["extract", "verify"], default="extract")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--concurrency", type=int, default=0, help="0 = the server's max_concurrency from /health")
    ap.add_argument("--images", nargs="*", default=None, help="image paths; default: bundled clean sample")
    ap.add_argument("--report", default="docs/LOADTEST.md")
    ap.add_argument("--interactive", action="store_true", help="no X-Batch header: measures the person-facing path")
    args = ap.parse_args()
    paths = (
        [Path(p) for p in args.images]
        if args.images
        else (
            [SAMPLES / "clean_front.png", SAMPLES / "clean_back.png"]
            if args.endpoint == "verify"
            else [SAMPLES / "clean_front.png"]
        )
    )
    files = [(p.name, p.read_bytes()) for p in paths]
    if args.concurrency <= 0:
        args.concurrency = int(httpx.get(f"{args.url}/api/v1/health", timeout=10).json().get("max_concurrency", 2))
    block = asyncio.run(steady(args, files) if args.mode == "steady" else burst(args, files))
    print(block)
    rp = Path(args.report)
    if not rp.exists():
        rp.write_text(
            "# Load test log\n\n_Appended by `tools/loadtest.py`. Each block names the host it ran against._\n\n",
            encoding="utf-8",
        )
    with rp.open("a", encoding="utf-8") as f:
        f.write(f"{block}\n- run at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")


if __name__ == "__main__":
    main()
