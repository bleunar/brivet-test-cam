"""
YOLOv8 + SAHI object detection engine, with live detection support.
"""

import logging
import os
import time
from pathlib import Path

# Prevent ultralytics from auto-updating packages
os.environ["YOLO_VERBOSE"] = "false"

import cv2
import numpy as np
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction
from ultralytics import YOLO

from app.config import CAPTURES_DIR, MODEL_PATH, DEFAULT_CONFIDENCE, DEFAULT_SLICES

logger = logging.getLogger(__name__)

# ── Model Loading ──────────────────────────────────────────────────────

_yolo_model: YOLO | None = None
_sahi_model: AutoDetectionModel | None = None


def _load_yolo() -> YOLO:
    """Load the raw YOLO model (lazy singleton)."""
    global _yolo_model
    if _yolo_model is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model file not found at {MODEL_PATH}. "
                "Place your .onnx file in the model/ directory."
            )
        logger.info("Loading YOLO model from %s ...", MODEL_PATH)
        _yolo_model = YOLO(str(MODEL_PATH), task="detect")
        logger.info("YOLO model loaded successfully.")
    return _yolo_model


def _load_sahi_model() -> AutoDetectionModel:
    """Load the SAHI-wrapped model (lazy singleton, reuses YOLO instance)."""
    global _sahi_model
    if _sahi_model is None:
        yolo = _load_yolo()
        _sahi_model = AutoDetectionModel.from_pretrained(
            model_type="yolov8",
            model=yolo,
            confidence_threshold=DEFAULT_CONFIDENCE,
            device="cpu",
        )
        logger.info("SAHI model wrapper loaded.")
    return _sahi_model


# ── SAHI Detection (for capture mode) ─────────────────────────────────


def run_detection(
    image_path: str,
    confidence: float = DEFAULT_CONFIDENCE,
    slices: int = DEFAULT_SLICES,
) -> dict:
    """
    Run sliced prediction on an image using SAHI + YOLOv8.

    Args:
        image_path: Path to the raw captured image.
        confidence: Minimum confidence threshold.
        slices: Number of slices per dimension (NxN grid).

    Returns:
        dict with keys: object_count, image_filename, duration_ms
    """
    model = _load_sahi_model()
    model.confidence_threshold = confidence

    logger.info(
        "Running detection: confidence=%.2f, slices=%dx%d on %s",
        confidence, slices, slices, image_path,
    )

    start = time.time()

    # Compute slice dimensions based on user setting
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    h, w = image.shape[:2]
    slice_h = max(h // slices, 1)
    slice_w = max(w // slices, 1)

    # Run SAHI sliced prediction
    result = get_sliced_prediction(
        image=image_path,
        detection_model=model,
        slice_height=slice_h,
        slice_width=slice_w,
        overlap_height_ratio=0.2,
        overlap_width_ratio=0.2,
    )

    # Draw detections on the image
    object_count = len(result.object_prediction_list)
    for pred in result.object_prediction_list:
        bbox = pred.bbox
        x1, y1, x2, y2 = int(bbox.minx), int(bbox.miny), int(bbox.maxx), int(bbox.maxy)
        score = pred.score.value
        label = pred.category.name or "Plastic Bottle"

        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 3)

        text = f"{label} {score:.0%}"
        (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(image, (x1, y1 - th - baseline - 8), (x1 + tw + 8, y1), (0, 255, 0), -1)
        cv2.putText(image, text, (x1 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    # Save annotated image
    timestamp = int(time.time() * 1000)
    filename = f"detection_{timestamp}.jpg"
    output_path = str(CAPTURES_DIR / filename)
    cv2.imwrite(output_path, image)

    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "Detection complete: %d objects found in %d ms → %s",
        object_count, duration_ms, filename,
    )

    # Clean up the temp raw image
    try:
        os.remove(image_path)
    except OSError:
        pass

    return {
        "object_count": object_count,
        "image_filename": filename,
        "duration_ms": duration_ms,
    }


# ── Live Detection (no SAHI, direct YOLO) ─────────────────────────────


def run_live_detection(
    frame: np.ndarray,
    confidence: float = DEFAULT_CONFIDENCE,
) -> tuple[np.ndarray, int]:
    """
    Run direct YOLO inference on a frame (no SAHI, no file I/O).

    Args:
        frame: BGR numpy array from the camera.
        confidence: Minimum confidence threshold.

    Returns:
        (annotated_frame, object_count) tuple.
    """
    model = _load_yolo()

    results = model.predict(frame, conf=confidence, verbose=False)

    object_count = 0
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue

        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            score = float(box.conf[0])
            cls_id = int(box.cls[0])
            label = result.names.get(cls_id, "Object")

            # Draw bounding box (green)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw label background
            text = f"{label} {score:.0%}"
            (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - th - baseline - 6), (x1 + tw + 6, y1), (0, 255, 0), -1)
            cv2.putText(frame, text, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

            object_count += 1

    return frame, object_count
