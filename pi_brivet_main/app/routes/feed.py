"""
API routes — Live camera feed (MJPEG stream).
"""

import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.camera import camera_manager

router = APIRouter(prefix="/api", tags=["feed"])


def _mjpeg_generator():
    """Yield MJPEG frames from the camera preview."""
    while True:
        frame = camera_manager.get_preview_frame()
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame
                + b"\r\n"
            )
        time.sleep(1 / 30)  # ~30 fps


@router.get("/feed")
async def video_feed():
    """Stream the live camera preview as MJPEG."""
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
