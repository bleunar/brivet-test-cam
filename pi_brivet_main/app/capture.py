"""
Capture manager — manual and automated image capture modes.
"""

import logging
import threading
import time
from datetime import datetime, timezone

from app.camera import camera_manager
from app.config import MIN_CAPTURE_INTERVAL, DEFAULT_CONFIDENCE, DEFAULT_SLICES
from app.database import SessionLocal
from app.detector import run_detection
from app.models import Detection

logger = logging.getLogger(__name__)


class CaptureManager:
    """Manages manual and automated capture workflows."""

    def __init__(self):
        self._lock = threading.Lock()
        self._last_capture_time: float = 0.0
        self._mode: str = "manual"  # "manual" or "automated"
        self._confidence: float = DEFAULT_CONFIDENCE
        self._slices: int = DEFAULT_SLICES

        # Automated capture state
        self._auto_thread: threading.Thread | None = None
        self._auto_running = False
        self._auto_interval: int = 0
        self._auto_max_captures: int = 0
        self._auto_captures_done: int = 0
        self._auto_next_capture_time: float = 0.0

        # Latest capture result (for status polling)
        self._last_result: dict | None = None
        self._is_processing = False

    # ── Settings ───────────────────────────────────────────────────────

    @property
    def confidence(self) -> float:
        return self._confidence

    @confidence.setter
    def confidence(self, value: float):
        self._confidence = max(0.01, min(1.0, value))

    @property
    def slices(self) -> int:
        return self._slices

    @slices.setter
    def slices(self, value: int):
        self._slices = max(1, min(8, value))

    # ── Status ─────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return the current capture status for the frontend."""
        now = time.time()
        cooldown_remaining = max(
            0, MIN_CAPTURE_INTERVAL - (now - self._last_capture_time)
        )

        status = {
            "mode": self._mode,
            "is_processing": self._is_processing,
            "cooldown_remaining": round(cooldown_remaining, 1),
            "confidence": self._confidence,
            "slices": self._slices,
            "last_result": self._last_result,
        }

        if self._mode == "automated":
            status.update({
                "auto_interval": self._auto_interval,
                "auto_max_captures": self._auto_max_captures,
                "auto_captures_done": self._auto_captures_done,
                "auto_remaining": self._auto_max_captures - self._auto_captures_done,
                "auto_next_capture_in": max(
                    0, round(self._auto_next_capture_time - now, 1)
                ) if self._auto_running else 0,
            })

        return status

    # ── Manual Capture ─────────────────────────────────────────────────

    def manual_capture(self) -> dict:
        """
        Trigger a single manual capture.

        Returns the detection result dict or raises an error.
        """
        if self._mode == "automated" and self._auto_running:
            raise RuntimeError("Cannot manually capture while automated mode is active.")

        now = time.time()
        elapsed = now - self._last_capture_time
        if elapsed < MIN_CAPTURE_INTERVAL:
            remaining = MIN_CAPTURE_INTERVAL - elapsed
            raise RuntimeError(
                f"Capture cooldown active. Please wait {remaining:.0f} more seconds."
            )

        return self._do_capture()

    # ── Automated Capture ──────────────────────────────────────────────

    def start_automated(self, interval: int, max_captures: int):
        """Start automated capture mode."""
        if interval < MIN_CAPTURE_INTERVAL:
            raise ValueError(
                f"Interval must be at least {MIN_CAPTURE_INTERVAL} seconds."
            )
        if max_captures < 1:
            raise ValueError("Maximum captures must be at least 1.")
        if self._auto_running:
            raise RuntimeError("Automated capture is already running.")

        self._mode = "automated"
        self._auto_interval = interval
        self._auto_max_captures = max_captures
        self._auto_captures_done = 0
        self._auto_running = True

        self._auto_thread = threading.Thread(target=self._automated_loop, daemon=True)
        self._auto_thread.start()
        logger.info(
            "Automated capture started: interval=%ds, max=%d",
            interval, max_captures,
        )

    def stop_automated(self):
        """Stop the automated capture mode."""
        self._auto_running = False
        if self._auto_thread:
            self._auto_thread.join(timeout=10)
            self._auto_thread = None
        self._mode = "manual"
        logger.info(
            "Automated capture stopped. Completed %d/%d captures.",
            self._auto_captures_done, self._auto_max_captures,
        )

    def _automated_loop(self):
        """Background loop for automated captures."""
        while self._auto_running and self._auto_captures_done < self._auto_max_captures:
            # Check cooldown from last capture
            now = time.time()
            elapsed = now - self._last_capture_time
            if elapsed < self._auto_interval:
                wait = self._auto_interval - elapsed
                self._auto_next_capture_time = now + wait
                # Sleep in small increments so we can be stopped
                end_time = now + wait
                while time.time() < end_time and self._auto_running:
                    time.sleep(0.5)
                if not self._auto_running:
                    break

            try:
                self._do_capture()
                self._auto_captures_done += 1
                logger.info(
                    "Automated capture %d/%d complete.",
                    self._auto_captures_done, self._auto_max_captures,
                )
            except Exception:
                logger.exception("Error during automated capture")
                time.sleep(2)

        # Finished or stopped
        self._auto_running = False
        self._mode = "manual"
        logger.info("Automated capture session ended.")

    # ── Core Capture ───────────────────────────────────────────────────

    def _do_capture(self) -> dict:
        """Capture image, run detection, save to DB. Returns result dict."""
        self._is_processing = True
        try:
            # 1. Capture high-res image from camera
            raw_path = camera_manager.capture_high_res()

            # 2. Run detection
            result = run_detection(raw_path, self._confidence, self._slices)

            # 3. Save to database
            db = SessionLocal()
            try:
                detection = Detection(
                    timestamp=datetime.now(timezone.utc),
                    object_count=result["object_count"],
                    confidence_threshold=self._confidence,
                    slice_count=self._slices,
                    image_filename=result["image_filename"],
                )
                db.add(detection)
                db.commit()
                db.refresh(detection)
                result["id"] = detection.id
                result["timestamp"] = detection.timestamp.isoformat()
            finally:
                db.close()

            self._last_capture_time = time.time()
            self._last_result = result
            return result

        finally:
            self._is_processing = False


# Singleton instance
capture_manager = CaptureManager()
