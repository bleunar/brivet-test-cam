"""
Raspberry Pi Camera — FastAPI Web App
Streams live MJPEG video and allows resolution / frame rate adjustments.
"""

import io
import threading
import time
import logging

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
        }

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


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
