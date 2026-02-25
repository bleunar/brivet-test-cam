"""
Camera manager — single background thread for continuous frame capture.

Provides low-res preview frames for the live MJPEG feed,
high-res still capture for detection processing, and
configurable main-stream frames for live detection.
"""

import io
import logging
import threading
import time

import numpy as np
from picamera2 import Picamera2

from app.config import (
    PREVIEW_WIDTH,
    PREVIEW_HEIGHT,
    CAPTURE_WIDTH,
    CAPTURE_HEIGHT,
    PREVIEW_QUALITY,
    TEMP_DIR,
    RESOLUTION_PRESETS,
    DEFAULT_LIVE_RESOLUTION,
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

        # Current main stream resolution
        self._main_width = CAPTURE_WIDTH
        self._main_height = CAPTURE_HEIGHT

    # ── Lifecycle ──────────────────────────────────────────────────────

    def start(self):
        """Initialize camera and start the background capture thread."""
        logger.info("Initializing camera...")
        self._camera = Picamera2()
        self._apply_config(self._main_width, self._main_height)
        self._camera.start()

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Camera started — preview %dx%d, main %dx%d",
                     PREVIEW_WIDTH, PREVIEW_HEIGHT, self._main_width, self._main_height)

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

    def _apply_config(self, main_w: int, main_h: int):
        """Apply camera configuration with the given main stream resolution."""
        config = self._camera.create_still_configuration(
            main={"size": (main_w, main_h), "format": "BGR888"},
            lores={"size": (PREVIEW_WIDTH, PREVIEW_HEIGHT), "format": "YUV420"},
            display="lores",
        )
        self._camera.configure(config)

    # ── Reconfigure ────────────────────────────────────────────────────

    def reconfigure(self, width: int, height: int):
        """
        Reconfigure the camera's main stream resolution.
        Briefly stops and restarts the camera.
        """
        if not self._camera:
            raise RuntimeError("Camera is not initialized")
        if width == self._main_width and height == self._main_height:
            return  # No change needed

        logger.info("Reconfiguring camera main stream to %dx%d...", width, height)
        with self._lock:
            self._camera.stop()
            self._apply_config(width, height)
            self._camera.start()
            self._main_width = width
            self._main_height = height
        logger.info("Camera reconfigured to %dx%d.", width, height)

    @property
    def main_resolution(self) -> tuple[int, int]:
        return (self._main_width, self._main_height)

    # ── Background loop ────────────────────────────────────────────────

    def _capture_loop(self):
        """Continuously capture low-res JPEG frames for the live preview."""
        while self._running and self._camera:
            try:
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

    def capture_main_frame_array(self) -> np.ndarray:
        """
        Capture a frame from the main stream as a numpy array.
        Used by live detection for in-memory inference (no disk I/O).
        """
        if not self._camera:
            raise RuntimeError("Camera is not initialized")
        return self._camera.capture_array("main")

    def capture_high_res(self) -> str:
        """
        Capture a full-resolution still image.
        Returns the absolute path to the saved JPEG in the temp directory.
        """
        if not self._camera:
            raise RuntimeError("Camera is not initialized")

        timestamp = int(time.time() * 1000)
        filepath = str(TEMP_DIR / f"capture_{timestamp}.jpg")
        self._camera.capture_file(filepath, name="main")
        logger.info("High-res capture saved: %s", filepath)
        return filepath


# Singleton instance
camera_manager = CameraManager()
