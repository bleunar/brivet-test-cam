"""
Raspberry Pi Camera — FastAPI Web App
Streams live MJPEG video and allows resolution / frame rate adjustments.
Supports single-image capture at maximum resolution.
"""

import io
import os
import threading
import time
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("pi-camera")

# ---------------------------------------------------------------------------
# App & templates
# ---------------------------------------------------------------------------
app = FastAPI(title="Pi Camera Stream")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------------------------
# Resolution presets
# ---------------------------------------------------------------------------
RESOLUTION_PRESETS = {
    "640x480":   (640, 480),
    "1280x720":  (1280, 720),
    "1920x1080": (1920, 1080),
}

DEFAULT_RESOLUTION = "1280x720"
DEFAULT_FRAMERATE  = 15
MIN_FRAMERATE      = 1
MAX_FRAMERATE      = 30

DEFAULT_SAVE_DIR   = os.path.expanduser("~/Pictures/brivet/test")
MAX_CAPTURE_SIZE   = (3280, 2464)   # Pi Camera V2 max

# ---------------------------------------------------------------------------
# Streaming output adapter
# ---------------------------------------------------------------------------
class StreamingOutput(io.BufferedIOBase):
    """Thread-safe buffer that receives JPEG frames from the encoder."""

    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


# ---------------------------------------------------------------------------
# Camera manager
# ---------------------------------------------------------------------------
class CameraManager:
    """Wraps Picamera2 lifecycle and provides frame iteration."""

    def __init__(self):
        self.lock = threading.Lock()
        self.picam2 = Picamera2()
        self.output = StreamingOutput()
        self.resolution_key = DEFAULT_RESOLUTION
        self.framerate = DEFAULT_FRAMERATE
        self._configure_and_start()

    # -- internal helpers ---------------------------------------------------

    def _configure_and_start(self):
        size = RESOLUTION_PRESETS[self.resolution_key]
        config = self.picam2.create_video_configuration(
            main={"size": size},
            controls={"FrameRate": self.framerate},
        )
        self.picam2.configure(config)
        self.output = StreamingOutput()
        encoder = MJPEGEncoder()
        self.picam2.start_recording(encoder, FileOutput(self.output))
        logger.info("Camera started — %s @ %d fps", self.resolution_key, self.framerate)

    # -- public API ---------------------------------------------------------

    def apply_settings(self, resolution_key: str, framerate: int):
        with self.lock:
            self.picam2.stop_recording()
            self.resolution_key = resolution_key
            self.framerate = max(MIN_FRAMERATE, min(MAX_FRAMERATE, framerate))
            self._configure_and_start()

    def get_settings(self) -> dict:
        return {
            "resolution": self.resolution_key,
            "framerate": self.framerate,
            "available_resolutions": list(RESOLUTION_PRESETS.keys()),
            "min_framerate": MIN_FRAMERATE,
            "max_framerate": MAX_FRAMERATE,
            "save_dir": DEFAULT_SAVE_DIR,
        }

    def capture_image(self, save_dir: str) -> str:
        """Capture a full-resolution PNG and return the file path."""
        with self.lock:
            # Stop the video stream
            self.picam2.stop_recording()

            # Switch to still configuration at max resolution
            still_config = self.picam2.create_still_configuration(
                main={"size": MAX_CAPTURE_SIZE},
            )
            self.picam2.configure(still_config)
            self.picam2.start()

            # Ensure save directory exists
            Path(save_dir).mkdir(parents=True, exist_ok=True)

            # Build filename
            now = datetime.now()
            filename = now.strftime("brivet_test_%Y-%m-%d_%H-%M-%S.png")
            filepath = os.path.join(save_dir, filename)

            # Capture
            self.picam2.capture_file(filepath)
            logger.info("Image captured — %s", filepath)

            # Return to video streaming
            self.picam2.stop()
            self._configure_and_start()

        return filepath

    def stream_frames(self):
        """Generator yielding MJPEG frames."""
        while True:
            with self.output.condition:
                self.output.condition.wait()
                frame = self.output.frame
            if frame is not None:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )


camera = CameraManager()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main control-panel UI."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "settings": camera.get_settings(),
    })


@app.get("/stream")
async def stream():
    """MJPEG video stream."""
    return StreamingResponse(
        camera.stream_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/settings")
async def get_settings():
    """Return current camera settings as JSON."""
    return JSONResponse(camera.get_settings())


@app.post("/settings")
async def update_settings(request: Request):
    """Apply new resolution and/or frame rate."""
    body = await request.json()

    resolution_key = body.get("resolution", camera.resolution_key)
    framerate = int(body.get("framerate", camera.framerate))

    if resolution_key not in RESOLUTION_PRESETS:
        return JSONResponse({"error": f"Unknown resolution: {resolution_key}"}, status_code=400)
    if not (MIN_FRAMERATE <= framerate <= MAX_FRAMERATE):
        return JSONResponse(
            {"error": f"Framerate must be between {MIN_FRAMERATE} and {MAX_FRAMERATE}"},
            status_code=400,
        )

    camera.apply_settings(resolution_key, framerate)
    logger.info("Settings applied — %s @ %d fps", resolution_key, framerate)
    return JSONResponse(camera.get_settings())


@app.post("/capture")
async def capture(request: Request):
    """Capture a single full-resolution PNG image."""
    body = await request.json()
    save_dir = body.get("save_dir", DEFAULT_SAVE_DIR).strip()

    if not save_dir:
        return JSONResponse({"error": "Save directory cannot be empty"}, status_code=400)

    try:
        filepath = camera.capture_image(save_dir)
    except Exception as exc:
        logger.exception("Capture failed")
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({"path": filepath})


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
