"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.formparsers import MultiPartParser

from app import __version__
from app.config import Settings, get_settings
from app.ocr.base import OcrEngine
from app.ocr.pool import OcrPool
from app.ocr.rapid import RapidEngine
from app.routes.api import router as api_router
from app.routes.csv_routes import router as csv_router
from app.security import ClientLimiter, SecurityMiddleware, install_error_handlers

logging.basicConfig(
    level=logging.INFO, format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
)
log = logging.getLogger("app")


def create_app(
    settings: Settings | None = None,
    *,
    warm: bool = True,
    engine_factory: Callable[[Settings], OcrEngine] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    make_engine = engine_factory or (lambda s: RapidEngine(s))
    # Multipart parts larger than this are spooled to disk by Starlette. Keep every image (per-image cap)
    # in memory so uploads never touch the filesystem; the request-size cap bounds total memory.
    MultiPartParser.spool_max_size = settings.max_image_bytes + 1024 * 1024

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = OcrPool(settings, lambda: make_engine(settings))
        app.state.pool = pool
        if warm:
            loop = asyncio.get_running_loop()
            # Warm in the background so health answers immediately with ready=false; verify returns 503 until warm.
            warm_task = loop.run_in_executor(None, pool.warmup)
            warm_task.add_done_callback(
                lambda fut: (
                    log.error("OCR warm-up failed; /ready stays 503: %s", fut.exception())
                    if fut.exception()
                    else log.info("OCR warm-up complete")
                )
            )
            app.state.warm_task = warm_task
        yield
        pool.shutdown()

    app = FastAPI(
        title="Label Check (prototype)",
        version=__version__,
        description=(
            "Prototype for verifying alcohol beverage label artwork against COLA application data. "
            "The tool recommends; the compliance agent decides. Nothing is stored."
        ),
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,  # no CDN-hosted docs UI (restricted networks)
        openapi_url="/api/v1/openapi.json",
    )
    app.state.settings = settings
    app.state.client_limiter = ClientLimiter(settings)
    app.add_middleware(SecurityMiddleware, settings=settings)
    install_error_handlers(app)
    app.include_router(api_router)
    app.include_router(csv_router)

    static_dir = settings.static_dir
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        async def index() -> FileResponse:
            return FileResponse(static_dir / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
