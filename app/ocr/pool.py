"""Worker pool and admission control for OCR.

One engine per worker thread, one ONNX intra-op thread per engine (measured to scale near
linearly, see docs/OCR_EVAL.md). A single capacity limiter of N slots protects the CPU:

- interactive requests may wait briefly for a slot;
- batch requests never wait: if fewer than ``reserved`` slots would remain for interactive use,
  they get an immediate BusyError (HTTP 429 with Retry-After) and the client backs off.

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
        self.reserved = min(settings.batch_reserved_interactive_slots, max(0, self.workers - 1))
        self.interactive_wait_s = 8.0
        self._factory = engine_factory
        self._executor = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="ocr")
        self._local = threading.local()
        self._sem = asyncio.Semaphore(self.workers)
        self._lock = threading.Lock()
        self._active_total = 0
        self._active_batch = 0
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
        return self._active_total

    def info(self) -> dict[str, str]:
        return dict(self._info)

    async def recognize(self, rgb: np.ndarray, *, interactive: bool) -> tuple[list[RawLine], int, int]:
        """Run OCR on one image. Returns (lines, queue_ms, ocr_ms). Raises BusyError when refused."""
        t0 = time.perf_counter()
        if not interactive:
            with self._lock:
                if self._active_total >= self.workers or self._active_batch >= self.workers - self.reserved:
                    raise BusyError(retry_after=1)
                self._active_total += 1
                self._active_batch += 1
            await self._sem.acquire()  # slot is guaranteed free by the counters above
        else:
            try:
                await asyncio.wait_for(self._sem.acquire(), timeout=self.interactive_wait_s)
            except TimeoutError as exc:
                raise BusyError(retry_after=2) from exc
            with self._lock:
                self._active_total += 1
        queue_ms = int((time.perf_counter() - t0) * 1000)
        try:
            t1 = time.perf_counter()
            loop = asyncio.get_running_loop()
            lines = await loop.run_in_executor(self._executor, self._run, rgb)
            return lines, queue_ms, int((time.perf_counter() - t1) * 1000)
        finally:
            with self._lock:
                self._active_total -= 1
                if not interactive:
                    self._active_batch -= 1
            self._sem.release()
