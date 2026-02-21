# Waste Detection Control Panel

A FastAPI web app for real-time waste detection (Paper / Plastic) using a custom YOLOv8 NCNN model on a Raspberry Pi Camera.

## Requirements

- Raspberry Pi (3/4/5) with Raspberry Pi OS (Bookworm or later)
- Raspberry Pi Camera Module connected and enabled
- Python 3.9+

## Model Setup

Copy the 4 model files from your training output into `models/waste_ncnn_model/`:

```
models/
└── waste_ncnn_model/
    ├── metadata.yaml
    ├── model.ncnn.bin
    ├── model.ncnn.param
    └── model_ncnn.py
```

> **Important:** The directory must end with `_ncnn_model` for ultralytics to recognize the NCNN format.

## Quick Start

```bash
# 1. Install system dependencies
sudo apt install -y python3-opencv

# 2. Create venv with system site-packages
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Open **http://\<pi-ip\>:9001** in a browser.

## Features

| Feature | Details |
|---------|---------|
| Live video | MJPEG stream with resolution selector |
| Waste detection | YOLOv8 NCNN — Paper & Plastic classes |
| Detection toggle | Switch between raw and annotated feed |
| Detection sidebar | Live list with class-coloured confidence bars |
| Confidence slider | Filter detections (10%–100%) |
| Resolution | 640×480 (45fps) · 1280×720 (30fps) · 1920×1080 (24fps) |
| Fullscreen | Expand video to fullscreen |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Control panel UI |
| `/stream/raw` | GET | Raw MJPEG stream |
| `/stream/detect` | GET | MJPEG stream with bounding boxes |
| `/detections` | GET | Latest detections (JSON) |
| `/confidence` | POST | Set confidence threshold (`{ threshold }`) |
| `/settings` | GET | Current camera settings |
| `/settings` | POST | Change resolution (`{ resolution }`) |
