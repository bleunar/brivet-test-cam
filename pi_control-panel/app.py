"""
Waste Detection Control Panel — FastAPI Web App
Live video with YOLOv8 NCNN waste detection (Paper / Plastic).
"""

import io
import threading
import time
import logging

import cv2
import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from picamera2 import Picamera2

from detector import DetectionEngine

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("pi-waste")

# ---------------------------------------------------------------------------
# App & templates
# ---------------------------------------------------------------------------
app = FastAPI(title="Waste Detection Control Panel")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RESOLUTION_PRESETS = {
    "640x480":   {"size": (640, 480),   "fps": 45},
    "1280x720":  {"size": (1280, 720),  "fps": 30},
    "1920x1080": {"size": (1920, 1080), "fps": 24},
}

DEFAULT_RESOLUTION = "1280x720"
DEFAULT_CONFIDENCE = 0.5

# ---------------------------------------------------------------------------
# Camera manager
# ---------------------------------------------------------------------------
class CameraManager:
    """Wraps Picamera2 and provides raw frames as numpy arrays."""

    def __init__(self):
        self.lock = threading.Lock()
        self.picam2 = Picamera2()
        self.resolution_key = DEFAULT_RESOLUTION
        self._configure_and_start()

    def _configure_and_start(self):
        preset = RESOLUTION_PRESETS[self.resolution_key]
        config = self.picam2.create_video_configuration(
            main={"size": preset["size"], "format": "BGR888"},
            controls={"FrameRate": preset["fps"]},
        )
        self.picam2.configure(config)
        self.picam2.start()
        logger.info("Camera started — %s @ %d fps", self.resolution_key, preset["fps"])

    def apply_resolution(self, resolution_key: str):
        """Stop, reconfigure, and restart the camera."""
        with self.lock:
            self.picam2.stop()
            self.resolution_key = resolution_key
            self._configure_and_start()

    def get_settings(self) -> dict:
        preset = RESOLUTION_PRESETS[self.resolution_key]
        return {
            "resolution": self.resolution_key,
            "fps": preset["fps"],
            "available_resolutions": {
                k: v["fps"] for k, v in RESOLUTION_PRESETS.items()
            },
        }

    def capture_array(self) -> np.ndarray:
        """Return the current frame as a BGR numpy array."""
        frame = self.picam2.capture_array()
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)


camera = CameraManager()
detector = DetectionEngine(confidence_threshold=DEFAULT_CONFIDENCE)

# ---------------------------------------------------------------------------
# Shared detection state
# ---------------------------------------------------------------------------
_detection_lock = threading.Lock()
_latest_detections: list[dict] = []


def _update_detections(dets: list[dict]):
    global _latest_detections
    with _detection_lock:
        _latest_detections = dets


def _get_detections() -> list[dict]:
    with _detection_lock:
        return list(_latest_detections)


# ---------------------------------------------------------------------------
# Stream generators
# ---------------------------------------------------------------------------

def _encode_jpeg(frame: np.ndarray) -> bytes:
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes()


def raw_frames():
    """Generator yielding raw MJPEG frames."""
    while True:
        frame = camera.capture_array()
        jpeg = _encode_jpeg(frame)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        )


def detection_frames():
    """Generator yielding MJPEG frames with bounding boxes."""
    while True:
        frame = camera.capture_array()
        detections = detector.detect(frame)
        _update_detections(detections)
        annotated = detector.draw(frame, detections)
        jpeg = _encode_jpeg(annotated)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main UI."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "confidence": detector.confidence_threshold,
        "settings": camera.get_settings(),
    })


@app.get("/stream/raw")
async def stream_raw():
    """Raw MJPEG video stream (no detection)."""
    return StreamingResponse(
        raw_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/stream/detect")
async def stream_detect():
    """MJPEG video stream with detection overlays."""
    return StreamingResponse(
        detection_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/detections")
async def get_detections():
    """Return the latest detection results as JSON."""
    return JSONResponse({"detections": _get_detections()})


@app.post("/confidence")
async def set_confidence(request: Request):
    """Update the detection confidence threshold."""
    body = await request.json()
    threshold = float(body.get("threshold", DEFAULT_CONFIDENCE))
    threshold = max(0.1, min(1.0, threshold))
    detector.confidence_threshold = threshold
    logger.info("Confidence threshold set to %.2f", threshold)
    return JSONResponse({"threshold": threshold})


@app.get("/settings")
async def get_settings():
    """Return current camera settings."""
    return JSONResponse(camera.get_settings())


@app.post("/settings")
async def update_settings(request: Request):
    """Change the camera resolution."""
    body = await request.json()
    resolution_key = body.get("resolution", camera.resolution_key)

    if resolution_key not in RESOLUTION_PRESETS:
        return JSONResponse({"error": f"Unknown resolution: {resolution_key}"}, status_code=400)

    camera.apply_resolution(resolution_key)
    logger.info("Resolution changed to %s", resolution_key)
    return JSONResponse(camera.get_settings())


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
