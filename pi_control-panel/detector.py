"""
Waste Detection Engine — YOLOv8 NCNN (Paper / Plastic)
Uses the ultralytics library to load and run the NCNN model.
"""

import os
import cv2
import numpy as np
from ultralytics import YOLO

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODELS_DIR, "model.ncnn.param")

# Class-specific colours (BGR for OpenCV)
CLASS_COLORS = {
    "Paper":   (53, 230, 163),   # green-ish
    "Plastic": (248, 189, 56),   # blue-ish (BGR for sky-blue)
}
DEFAULT_COLOR = (124, 92, 252)   # purple fallback


class DetectionEngine:
    """Wraps YOLOv8 NCNN inference for waste detection."""

    def __init__(self, confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold
        self.model = YOLO(MODEL_PATH, task="detect")

        # Class names from the model metadata
        self.names = self.model.names  # {0: 'Paper', 1: 'Plastic'}

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Run inference on a BGR frame.
        Returns a list of dicts: {label, confidence, bbox: [x1, y1, x2, y2]}
        with pixel coordinates.
        """
        results = self.model.predict(
            frame,
            conf=self.confidence_threshold,
            verbose=False,
        )

        detections = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label = self.names.get(cls_id, f"id:{cls_id}")
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append({
                    "label": label,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                })

        return detections

    def draw(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Draw bounding boxes and labels onto the frame (in-place)."""
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            label = det["label"]
            conf = det["confidence"]

            color = CLASS_COLORS.get(label, DEFAULT_COLOR)
            thickness = 2

            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

            # Label background
            label_text = f"{label} {conf:.0%}"
            (tw, th), baseline = cv2.getTextSize(
                label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1
            )
            cv2.rectangle(
                frame,
                (x1, y1 - th - baseline - 6),
                (x1 + tw + 6, y1),
                color, -1,
            )

            # Label text
            cv2.putText(
                frame, label_text,
                (x1 + 3, y1 - baseline - 3),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA,
            )

        return frame
