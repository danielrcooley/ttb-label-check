"""Worker pool and admission control for OCR.

One engine per worker thread, one ONNX intra-op thread per engine (measured to scale near
linearly, see docs/OCR_EVAL.md). A single capacity limiter of N slots protects the CPU.

Priority policy (pinned by tests/unit/test_pool.py):
- Interactive requests may wait briefly for a slot (a person is watching a spinner).
- Batch requests never wait. They are refused with BusyError (HTTP 429 + Retry-After) when every
  slot is busy, or when an interactive request is already waiting, so the next free slot goes to
  the person rather than to the queue. When nobody is waiting, batch may use every slot.

Health checks never touch the pool, so they answer even when it is saturated.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from app.config import Settings

from .base import OcrEngine, RawLine

log = logging.getLogger(__name__)


class BusyError(Exception):
    def __init__(self, retry_after: int = 1) -> None:
        super().__init__("OCR capacity is fully in use")
        self.retry_after = retry_after


class OcrPool:
    def __init__(self, settings: Settings, engine_factory: Callable[[], OcrEngine]) -> None:
        self.workers = max(1, settings.ocr_workers)
        self.interactive_wait_s = settings.interactive_wait_seconds
        self._factory = engine_factory
        self._executor = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="ocr")
        self._local = threading.local()
        self._sem = asyncio.Semaphore(self.workers)
        self._lock = threading.Lock()
        self._active = 0  # admitted requests holding (or about to hold) a slot
        self._interactive_waiting = 0
        self._info: dict[str, str] = {}
        self.ready = False

    # ------------------------------------------------------------------ engines
    def _engine(self) -> OcrEngine:
        eng = getattr(self._local, "engine", None)
        if eng is None:
            eng = self._factory()
            self._local.engine = eng
            self._info = eng.info()
        return eng

    def _run(self, rgb: np.ndarray) -> list[RawLine]:
        return self._engine().recognize(rgb)

    def warmup(self) -> None:
        """Build one engine per worker thread and run a tiny image through each."""
        blank = np.full((64, 256, 3), 255, dtype=np.uint8)
        barrier = threading.Barrier(self.workers)

        def job() -> None:
            self._engine().recognize(blank)
            barrier.wait(timeout=120)  # hold the thread so every worker gets its own engine

        futures = [self._executor.submit(job) for _ in range(self.workers)]
        for f in futures:
            f.result(timeout=180)
        self.ready = True
        log.info("OCR pool ready: %d worker(s), %s", self.workers, self._info)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ admission
    @property
    def in_flight(self) -> int:
        return self._active

    @property
    def interactive_waiting(self) -> int:
        return self._interactive_waiting

    def info(self) -> dict[str, str]:
        return dict(self._info)

    async def _admit(self, interactive: bool) -> None:
        if interactive:
            with self._lock:
                self._interactive_waiting += 1
            try:
                await asyncio.wait_for(self._sem.acquire(), timeout=self.interactive_wait_s)
            except TimeoutError as exc:
                raise BusyError(retry_after=2) from exc
            finally:
                with self._lock:
                    self._interactive_waiting -= 1
            with self._lock:
                self._active += 1
            return
        with self._lock:
            if self._active >= self.workers or self._interactive_waiting > 0:
                raise BusyError(retry_after=1)
            self._active += 1  # reserve before awaiting so concurrent batch callers cannot all pass
        await self._sem.acquire()  # cannot block: holders + reservations never exceed the slot count

    async def recognize(self, rgb: np.ndarray, *, interactive: bool) -> tuple[list[RawLine], int, int]:
        """Run OCR on one image. Returns (lines, queue_ms, ocr_ms). Raises BusyError when refused."""
        t0 = time.perf_counter()
        await self._admit(interactive)
        queue_ms = int((time.perf_counter() - t0) * 1000)
        try:
            t1 = time.perf_counter()
            loop = asyncio.get_running_loop()
            lines = await loop.run_in_executor(self._executor, self._run, rgb)
            return lines, queue_ms, int((time.perf_counter() - t1) * 1000)
        finally:
            with self._lock:
                self._active -= 1
            self._sem.release()
