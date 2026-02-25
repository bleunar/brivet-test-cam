"""
Application configuration and settings.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CAPTURES_DIR = DATA_DIR / "captures"
MODEL_DIR = BASE_DIR / "model"
STATIC_DIR = BASE_DIR / "static"

# Temp directory on RAM (tmpfs) for raw captures before processing
TEMP_DIR = Path("/dev/shm/brivet")

# Database
DB_PATH = DATA_DIR / "detections.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Model
MODEL_PATH = MODEL_DIR / "best.onnx"

# ── Camera ─────────────────────────────────────────────────────────────
PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 480
CAPTURE_WIDTH = 3280
CAPTURE_HEIGHT = 2464
PREVIEW_FPS = 24
PREVIEW_QUALITY = 60  # JPEG quality for live feed

# ── Detection Defaults ─────────────────────────────────────────────────
DEFAULT_CONFIDENCE = 0.25
DEFAULT_SLICES = 2  # NxN grid for SAHI

# ── Capture Constraints ────────────────────────────────────────────────
MIN_CAPTURE_INTERVAL = 45  # seconds

# ── Live Detection ─────────────────────────────────────────────────────
RESOLUTION_PRESETS = {
    "640x480": (640, 480),
    "1280x720": (1280, 720),
    "1280x1280": (1280, 1280),
    "1920x1080": (1920, 1080),
}
DEFAULT_LIVE_RESOLUTION = "1280x1280"

# ── Ensure directories exist ───────────────────────────────────────────
for d in (DATA_DIR, CAPTURES_DIR, MODEL_DIR, TEMP_DIR):
    d.mkdir(parents=True, exist_ok=True)
