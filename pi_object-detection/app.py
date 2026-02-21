"""
Raspberry Pi Object Detection — FastAPI Web App
Live video with TFLite MobileNet SSD v1 (COCO) object detection.
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
logger = logging.getLogger("pi-detect")

# ---------------------------------------------------------------------------
# App & templates
# ---------------------------------------------------------------------------
app = FastAPI(title="Pi Object Detection")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RESOLUTION = (1280, 720)
FRAMERATE = 24
DEFAULT_CONFIDENCE = 0.5

# ---------------------------------------------------------------------------
# Camera manager
# ---------------------------------------------------------------------------
class CameraManager:
    """Wraps Picamera2 and provides raw frames as numpy arrays."""

    def __init__(self):
        self.picam2 = Picamera2()
        config = self.picam2.create_video_configuration(
            main={"size": RESOLUTION, "format": "RGB888"},
            controls={"FrameRate": FRAMERATE},
        )
        self.picam2.configure(config)
        self.picam2.start()
        logger.info("Camera started — %dx%d @ %d fps", *RESOLUTION, FRAMERATE)

    def capture_array(self) -> np.ndarray:
        """Return the current frame as a BGR numpy array."""
        rgb = self.picam2.capture_array()
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


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


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
