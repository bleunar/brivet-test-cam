# Pi Brivet — Object Detection Control Panel

A web-based control panel for Raspberry Pi that uses a **YOLOv8** model with **SAHI** (Slicing Aided Hyper Inference) to detect plastic bottles from a **Pi Camera v2**. Built with **FastAPI** and a modern dark-themed dashboard.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![YOLOv8](https://img.shields.io/badge/YOLOv8-ONNX-orange)

---

## Features

- **Live Camera Feed** — Real-time MJPEG preview from the Pi Camera
- **Manual Capture** — One-click image capture and processing
- **Automated Capture** — Configurable interval and maximum capture count
- **YOLOv8 + SAHI** — Sliced inference for high-resolution object detection
- **Detection Overlays** — Bounding boxes and labels drawn on captured images
- **Capture History** — Browse, view, and delete past detections
- **Tunable Settings** — Adjustable confidence threshold and SAHI slice grid
- **SQLite Database** — Persistent record of all detection results
- **Future-Ready** — GPS fields in the database for planned heatmap integration

---

## Prerequisites

- **Hardware**: Raspberry Pi 4 Model B + Pi Camera Module v2
- **OS**: Raspberry Pi OS (Bookworm or later, with `libcamera` stack)
- **Python**: 3.9 or higher

Verify camera access:

```bash
libcamera-hello --timeout 2000
```

---

## Setup

### 1. Clone / Copy the Project

```bash
cd /path/to/your/projects
# If cloning from a repo:
git clone <repo-url> pi_brivet_main
cd pi_brivet_main
```

### 2. Create Virtual Environment

> **Important:** The `--system-site-packages` flag is **required** so that the venv can access
> system-installed packages like `libcamera` and `picamera2`, which are not available via pip.

```bash
python -m venv --system-site-packages venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** If you encounter a `numpy.dtype size changed` error on startup, the system
> `numpy` and `simplejpeg` packages are out of sync. Upgrade both inside the venv:
>
> ```bash
> pip install --upgrade numpy simplejpeg
> ```

### 4. Place Your ONNX Model

Copy your YOLOv8 `.onnx` model file into the `model/` directory and name it `best.onnx`:

```bash
cp /path/to/your/model.onnx model/best.onnx
```

> **Note**: The default model path can be changed in `app/config.py` → `MODEL_PATH`.

---

## Running

```bash
# Option 1: Using the convenience script
bash run.sh

# Option 2: Directly with uvicorn
python -m uvicorn app.main:app --host 0.0.0.0 --port 9000
```

Open your browser and navigate to:

```
http://<raspberry-pi-ip>:9000
```

---

## Usage

### Live Feed

The dashboard shows a live MJPEG stream from your Pi Camera at the top left. The camera runs on a background thread with low-resolution preview frames for smooth streaming.

### Capture Modes

**Manual Mode** (default):
- Click the **Capture Image** button to take a photo and run detection.
- A 45-second cooldown is enforced between captures.

**Automated Mode**:
1. Switch to the **Automated** tab.
2. Set the **Capture Interval** (minimum 45 seconds).
3. Set the **Maximum Captures** count.
4. Click **Start Automated Capture**.
5. The system captures and processes images automatically until the max is reached or you click **Stop**.

### Detection Settings

- **Confidence Threshold** — Adjust the minimum confidence (1%–100%) to filter detections.
- **SAHI Slice Grid** — Set the NxN slicing grid (1–8). Higher values detect smaller objects but take longer to process. A warning dialog appears for grids ≥ 4×4.

### History

- All captures are shown in the **Capture History** panel with thumbnails.
- Click any thumbnail to view the full annotated image in a lightbox.
- Delete individual records using the × button on hover.

---

## Project Structure

```
pi_brivet_main/
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── config.py         # Settings & paths
│   ├── database.py       # SQLAlchemy setup
│   ├── models.py         # ORM models
│   ├── camera.py         # Camera background thread
│   ├── detector.py       # YOLOv8 + SAHI engine
│   ├── capture.py        # Capture manager
│   └── routes/
│       ├── feed.py       # MJPEG stream
│       ├── capture.py    # Capture endpoints
│       ├── history.py    # History CRUD
│       └── settings.py   # Detection settings
├── static/               # Frontend assets
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── data/                 # Runtime data (auto-created)
│   ├── detections.db
│   └── captures/
├── model/                # Place .onnx model here
├── requirements.txt
├── run.sh
└── README.md
```

---

## Data Storage

| What | Where |
|---|---|
| SQLite database | `data/detections.db` |
| Annotated images | `data/captures/` |
| Temp raw captures | `/dev/shm/brivet/` (RAM) |

---

## Future Integrations

- **GPS Module**: Track geo-location of each capture via a GPS module.
- **Heatmap**: Visualize detection density on a map in the control panel.
- Database fields (`latitude`, `longitude`) are already in place.

---

## License

This project is proprietary. All rights reserved.
