# Pi Test Camera

A FastAPI web app that streams a live Raspberry Pi Camera feed and lets you adjust resolution and frame rate from a browser-based control panel.

## Requirements

- Raspberry Pi (3/4/5) with Raspberry Pi OS (Bookworm or later)
- Raspberry Pi Camera Module connected and enabled
- Python 3.9+

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Open **http://\<pi-ip\>:9000** in a browser.

## Features

| Feature | Details |
|---------|---------|
| Live video | MJPEG stream via `<img>` tag |
| Resolution | 640×480 · 1280×720 · 1920×1080 |
| Frame rate | 1–60 fps (max depends on resolution: 640×480→60, 720p→45, 1080p→30) |
| Image capture | Full-resolution PNG, configurable save directory |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Control panel UI |
| `/stream` | GET | MJPEG video stream |
| `/settings` | GET | Current settings (JSON) |
| `/settings` | POST | Apply new settings (JSON body: `{ resolution, framerate }`) |
| `/capture` | POST | Capture full-res PNG (JSON body: `{ save_dir }`) |
