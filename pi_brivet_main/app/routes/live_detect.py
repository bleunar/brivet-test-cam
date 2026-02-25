"""
API routes — Live object detection (real-time YOLO on camera feed).
"""

import logging
import threading
import time

import cv2
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.camera import camera_manager
from app.config import (
    DEFAULT_CONFIDENCE,
    DEFAULT_LIVE_RESOLUTION,
    RESOLUTION_PRESETS,
)
from app.detector import run_live_detection

router = APIRouter(prefix="/api/live", tags=["live"])
logger = logging.getLogger(__name__)


# ── State ──────────────────────────────────────────────────────────────

class _LiveState:
    """Mutable shared state for live detection mode."""

    def __init__(self):
        self.active = False
        self.confidence = DEFAULT_CONFIDENCE
        self.resolution = DEFAULT_LIVE_RESOLUTION
        self.fps = 0.0
        self.object_count = 0
        self.lock = threading.Lock()


_state = _LiveState()


# ── Request Models ─────────────────────────────────────────────────────

class LiveSettingsUpdate(BaseModel):
    confidence: float | None = Field(None, ge=0.01, le=1.0)
    resolution: str | None = None


# ── MJPEG Generator ───────────────────────────────────────────────────

def _live_detection_generator():
    """
    Yield MJPEG frames with YOLO detection overlays.
    Runs inference on each main-stream frame.
    """
    frame_count = 0
    fps_start = time.time()

    while _state.active:
        try:
            # Grab a frame from the main camera stream
            frame = camera_manager.capture_main_frame_array()

            # Convert RGB (picamera2) → BGR (OpenCV)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Run YOLO detection
            annotated, count = run_live_detection(frame, _state.confidence)

            with _state.lock:
                _state.object_count = count

            # Encode as JPEG
            _, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            jpeg_bytes = jpeg.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + jpeg_bytes
                + b"\r\n"
            )

            # FPS tracking
            frame_count += 1
            elapsed = time.time() - fps_start
            if elapsed >= 1.0:
                with _state.lock:
                    _state.fps = round(frame_count / elapsed, 1)
                frame_count = 0
                fps_start = time.time()

        except Exception:
            logger.exception("Error in live detection loop")
            time.sleep(0.5)


# ── Endpoints ──────────────────────────────────────────────────────────

@router.get("/feed")
async def live_feed():
    """Stream the live detection MJPEG feed."""
    if not _state.active:
        _state.active = True
    return StreamingResponse(
        _live_detection_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/start")
async def start_live():
    """Enable live detection mode."""
    if _state.active:
        return {"status": "ok", "message": "Already active."}

    # Reconfigure camera to live detection resolution
    res = RESOLUTION_PRESETS.get(_state.resolution)
    if res:
        camera_manager.reconfigure(*res)

    _state.active = True
    logger.info("Live detection started at %s", _state.resolution)
    return {"status": "ok", "message": "Live detection started."}


@router.post("/stop")
async def stop_live():
    """Disable live detection mode and restore capture resolution."""
    _state.active = False

    # Restore full-res for captures
    from app.config import CAPTURE_WIDTH, CAPTURE_HEIGHT
    camera_manager.reconfigure(CAPTURE_WIDTH, CAPTURE_HEIGHT)

    logger.info("Live detection stopped, camera restored to full resolution.")
    return {"status": "ok", "message": "Live detection stopped."}


@router.get("/status")
async def live_status():
    """Return current live detection status."""
    with _state.lock:
        return {
            "active": _state.active,
            "confidence": _state.confidence,
            "resolution": _state.resolution,
            "fps": _state.fps,
            "object_count": _state.object_count,
            "available_resolutions": list(RESOLUTION_PRESETS.keys()),
        }


@router.put("/settings")
async def update_live_settings(body: LiveSettingsUpdate):
    """Update live detection confidence and/or resolution."""
    updated = {}

    if body.confidence is not None:
        _state.confidence = body.confidence
        updated["confidence"] = _state.confidence

    if body.resolution is not None:
        if body.resolution not in RESOLUTION_PRESETS:
            return {
                "status": "error",
                "message": f"Invalid resolution. Options: {list(RESOLUTION_PRESETS.keys())}",
            }
        _state.resolution = body.resolution
        updated["resolution"] = body.resolution

        # Reconfigure camera if live detection is active
        if _state.active:
            res = RESOLUTION_PRESETS[body.resolution]
            camera_manager.reconfigure(*res)

    return {"status": "ok", "settings": updated}
