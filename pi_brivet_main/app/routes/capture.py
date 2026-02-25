"""
API routes — Image capture (manual & automated).
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.capture import capture_manager
from app.config import MIN_CAPTURE_INTERVAL

router = APIRouter(prefix="/api/capture", tags=["capture"])
logger = logging.getLogger(__name__)


# ── Request Models ─────────────────────────────────────────────────────

class AutoStartRequest(BaseModel):
    interval: int = Field(
        ...,
        ge=MIN_CAPTURE_INTERVAL,
        description=f"Seconds between captures (minimum {MIN_CAPTURE_INTERVAL})",
    )
    max_captures: int = Field(
        ...,
        ge=1,
        description="Total number of captures before stopping",
    )


# ── Endpoints ──────────────────────────────────────────────────────────

@router.post("")
async def trigger_capture():
    """Trigger a manual capture and return the detection result."""
    try:
        result = capture_manager.manual_capture()
        return {"status": "ok", "data": result}
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}


@router.post("/auto/start")
async def start_automated(body: AutoStartRequest):
    """Start automated capture mode."""
    try:
        capture_manager.start_automated(body.interval, body.max_captures)
        return {"status": "ok", "message": "Automated capture started."}
    except (ValueError, RuntimeError) as e:
        return {"status": "error", "message": str(e)}


@router.post("/auto/stop")
async def stop_automated():
    """Stop automated capture mode."""
    capture_manager.stop_automated()
    return {"status": "ok", "message": "Automated capture stopped."}


@router.get("/status")
async def capture_status():
    """Return current capture status."""
    return capture_manager.get_status()
