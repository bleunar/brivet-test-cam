"""
Pi Brivet — FastAPI Application Entry Point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import STATIC_DIR
from app.database import init_db
from app.camera import camera_manager

# ── Logging ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("brivet")


# ── Lifespan ───────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB & camera. Shutdown: release camera."""
    logger.info("Starting Pi Brivet...")
    init_db()
    camera_manager.start()
    logger.info("Pi Brivet is ready.")
    yield
    logger.info("Shutting down Pi Brivet...")
    camera_manager.stop()
    logger.info("Goodbye.")


# ── App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Pi Brivet",
    description="Raspberry Pi object detection control panel",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Routes ─────────────────────────────────────────────────────────────

from app.routes.feed import router as feed_router
from app.routes.capture import router as capture_router
from app.routes.history import router as history_router
from app.routes.settings import router as settings_router

app.include_router(feed_router)
app.include_router(capture_router)
app.include_router(history_router)
app.include_router(settings_router)

# ── Static Files & SPA ────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    """Serve the single-page application."""
    return FileResponse(str(STATIC_DIR / "index.html"))
