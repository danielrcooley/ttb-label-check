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
