"""Admission policy of the OCR pool, with a fake engine that just sleeps."""

from __future__ import annotations

import asyncio
import time

import numpy as np
import pytest
from app.config import Settings
from app.ocr.base import RawLine
from app.ocr.pool import BusyError, OcrPool


class SleepyEngine:
    name = "sleepy"

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    def recognize(self, rgb: np.ndarray) -> list[RawLine]:
        time.sleep(self.seconds)
        return [RawLine(text="x", confidence=1.0, box=((0, 0), (1, 0), (1, 1), (0, 1)))]

    def info(self) -> dict[str, str]:
        return {"engine": "sleepy"}


IMG = np.zeros((8, 8, 3), dtype=np.uint8)


def make_pool(workers: int, seconds: float = 0.3, wait: float = 5.0) -> OcrPool:
    pool = OcrPool(Settings(ocr_workers=workers, interactive_wait_seconds=wait), lambda: SleepyEngine(seconds))
    pool.warmup()
    return pool


def test_batch_may_use_every_slot_when_nobody_is_waiting():
    async def go():
        pool = make_pool(2)
        results = await asyncio.gather(pool.recognize(IMG, interactive=False), pool.recognize(IMG, interactive=False))
        assert all(lines for lines, _, _ in results)
        pool.shutdown()

    asyncio.run(go())


def test_batch_is_refused_immediately_when_all_slots_are_busy():
    async def go():
        pool = make_pool(1, seconds=0.5)
        first = asyncio.create_task(pool.recognize(IMG, interactive=False))
        await asyncio.sleep(0.05)
        with pytest.raises(BusyError) as e:
            await pool.recognize(IMG, interactive=False)
        assert e.value.retry_after >= 1
        await first
        pool.shutdown()

    asyncio.run(go())


def test_interactive_waits_for_a_slot_and_blocks_new_batch_admissions_meanwhile():
    async def go():
        pool = make_pool(1, seconds=0.4)
        batch = asyncio.create_task(pool.recognize(IMG, interactive=False))
        await asyncio.sleep(0.05)
        interactive = asyncio.create_task(pool.recognize(IMG, interactive=True))
        await asyncio.sleep(0.05)
        assert pool.interactive_waiting == 1
        with pytest.raises(BusyError):  # a new batch request must not jump the queue
            await pool.recognize(IMG, interactive=False)
        lines, queue_ms, _ = await interactive
        assert lines and queue_ms >= 200  # it waited for the batch job to finish
        await batch
        pool.shutdown()

    asyncio.run(go())


def test_interactive_gives_up_after_the_wait_budget():
    async def go():
        pool = make_pool(1, seconds=1.0, wait=0.2)
        hog = asyncio.create_task(pool.recognize(IMG, interactive=False))
        await asyncio.sleep(0.05)
        with pytest.raises(BusyError) as e:
            await pool.recognize(IMG, interactive=True)
        assert e.value.retry_after == 2
        await hog
        pool.shutdown()

    asyncio.run(go())


def test_warmup_failure_is_recorded_and_visible_in_health():
    import time as _time

    from app.main import create_app
    from fastapi.testclient import TestClient

    class Broken:
        name = "broken"

        def __init__(self, settings):
            raise ImportError("libgthread-2.0.so.0: cannot open shared object file")

    app = create_app(Settings(ocr_workers=1), engine_factory=Broken)
    with TestClient(app) as c:
        for _ in range(50):
            body = c.get("/api/v1/health").json()
            if body["status"] == "failed":
                break
            _time.sleep(0.1)
        assert body["status"] == "failed" and body["ready"] is False
        assert "libgthread" in body["error"]
        r = c.get("/api/v1/ready")
        assert r.status_code == 503 and "libgthread" in r.json()["message"]


def test_cancelled_request_keeps_its_slot_until_the_thread_finishes():
    async def go():
        pool = make_pool(1, seconds=0.6)
        task = asyncio.create_task(pool.recognize(IMG, interactive=False))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(BusyError):  # the OCR thread is still running; capacity is not free
            await pool.recognize(IMG, interactive=False)
        await asyncio.sleep(0.8)
        lines, _, _ = await pool.recognize(IMG, interactive=False)  # released once the thread ended
        assert lines
        pool.shutdown()

    asyncio.run(go())


def test_batch_request_holds_one_slot_across_all_its_images():
    async def go():
        pool = make_pool(1, seconds=0.3)

        async def two_images():
            async with pool.slot(interactive=False) as (run, _q):
                first = await run(IMG)
                second = await run(IMG)  # must not be refused: the slot is still ours
                return first, second

        t = asyncio.create_task(two_images())
        await asyncio.sleep(0.05)
        with pytest.raises(BusyError):  # a competing batch request sees no free slot in between
            await pool.recognize(IMG, interactive=False)
        first, second = await t
        assert first and second
        pool.shutdown()

    asyncio.run(go())
