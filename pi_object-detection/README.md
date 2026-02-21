# Pi Object Detection

A FastAPI web app that performs real-time object detection on a Raspberry Pi Camera feed using TFLite MobileNet SSD v1 (COCO 80 classes).

## Requirements

- Raspberry Pi (3/4/5) with Raspberry Pi OS (Bookworm or later)
- Raspberry Pi Camera Module connected and enabled
- Python 3.9+

## Quick Start

```bash
# 1. Download the TFLite model
chmod +x models/download_model.sh
./models/download_model.sh

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py
```

Open **http://\<pi-ip\>:9000** in a browser.

## Features

| Feature | Details |
|---------|---------|
| Live video | 1280×720 @ 24fps MJPEG stream |
| Object detection | TFLite MobileNet SSD v1 (COCO 80 classes) |
| Detection toggle | Switch between raw and annotated feed |
| Detection sidebar | Live list of detected objects with confidence bars |
| Confidence slider | Filter detections by confidence (10%–100%) |
| Fullscreen | Expand the video feed to fullscreen |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Control panel UI |
| `/stream/raw` | GET | Raw MJPEG stream |
| `/stream/detect` | GET | MJPEG stream with bounding boxes |
| `/detections` | GET | Latest detections (JSON) |
| `/confidence` | POST | Set confidence threshold (`{ threshold }`) |
