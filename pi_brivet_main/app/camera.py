"""
Camera manager — single background thread for continuous frame capture.

Provides low-res preview frames for the live MJPEG feed and
high-res still capture for detection processing.
"""

import io
import logging
import threading
import time

from picamera2 import Picamera2
from libcamera import controls as libcamera_controls

from app.config import (
    PREVIEW_WIDTH,
    PREVIEW_HEIGHT,
    CAPTURE_WIDTH,
    CAPTURE_HEIGHT,
    PREVIEW_QUALITY,
    TEMP_DIR,
)

logger = logging.getLogger(__name__)


class CameraManager:
    """Thread-safe camera manager using Picamera2."""

    def __init__(self):
        self._camera: Picamera2 | None = None
        self._lock = threading.Lock()
        self._frame: bytes = b""
        self._running = False
        self._thread: threading.Thread | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────

    def start(self):
        """Initialize camera and start the background capture thread."""
        logger.info("Initializing camera...")
        self._camera = Picamera2()

        # Configure dual-output: low-res for preview, high-res for stills
        config = self._camera.create_still_configuration(
            main={"size": (CAPTURE_WIDTH, CAPTURE_HEIGHT), "format": "RGB888"},
            lores={"size": (PREVIEW_WIDTH, PREVIEW_HEIGHT), "format": "YUV420"},
            display="lores",
        )
        self._camera.configure(config)
        self._camera.set_controls({"AfMode": libcamera_controls.AfModeEnum.Continuous})
        self._camera.start()

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Camera started — preview %dx%d, capture %dx%d",
                     PREVIEW_WIDTH, PREVIEW_HEIGHT, CAPTURE_WIDTH, CAPTURE_HEIGHT)

    def stop(self):
        """Stop the background thread and release the camera."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._camera:
            self._camera.stop()
            self._camera.close()
            self._camera = None
        logger.info("Camera stopped.")

    # ── Background loop ────────────────────────────────────────────────

    def _capture_loop(self):
        """Continuously capture low-res JPEG frames for the live preview."""
        while self._running and self._camera:
            try:
                # Grab the low-res (lores) stream as a JPEG
                buf = io.BytesIO()
                self._camera.capture_file(buf, format="jpeg", name="lores")
                with self._lock:
                    self._frame = buf.getvalue()
                time.sleep(1 / 30)  # ~30 fps target
            except Exception:
                logger.exception("Error in preview capture loop")
                time.sleep(0.5)

    # ── Public API ─────────────────────────────────────────────────────

    def get_preview_frame(self) -> bytes:
        """Return the latest low-res JPEG frame (thread-safe)."""
        with self._lock:
            return self._frame

    def capture_high_res(self) -> str:
        """
        Capture a full-resolution still image.

        Returns the absolute path to the saved JPEG in the temp directory.
        """
        if not self._camera:
            raise RuntimeError("Camera is not initialized")

        timestamp = int(time.time() * 1000)
        filepath = str(TEMP_DIR / f"capture_{timestamp}.jpg")

        # request() grabs a high-res frame from the main stream
        self._camera.capture_file(filepath, name="main")
        logger.info("High-res capture saved: %s", filepath)
        return filepath


# Singleton instance
camera_manager = CameraManager()
