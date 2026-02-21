"""
Detection Engine — TFLite MobileNet SSD v1 (COCO)
Loads the model once and provides detect() / draw() helpers.
"""

import os
import numpy as np
import cv2

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    # Fallback for full TensorFlow installs
    import tensorflow as tf
    Interpreter = tf.lite.Interpreter


MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODELS_DIR, "detect.tflite")
LABELS_PATH = os.path.join(MODELS_DIR, "labelmap.txt")

# Bounding-box colour palette (10 distinct colours, cycled by class index)
BOX_COLORS = [
    (124, 92, 252),   # purple/accent
    (16, 185, 129),   # emerald
    (239, 68, 68),    # red
    (251, 191, 36),   # amber
    (56, 189, 248),   # sky
    (244, 114, 182),  # pink
    (163, 230, 53),   # lime
    (251, 146, 60),   # orange
    (129, 140, 248),  # indigo
    (45, 212, 191),   # teal
]


class DetectionEngine:
    """Wraps TFLite inference for MobileNet SSD v1 (COCO)."""

    def __init__(self, confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold

        # Load labels (skip first entry if it's '???')
        with open(LABELS_PATH, "r") as f:
            raw = [line.strip() for line in f.readlines()]
        if raw and raw[0] == "???":
            raw = raw[1:]
        self.labels = raw

        # Load model
        self.interpreter = Interpreter(model_path=MODEL_PATH)
        self.interpreter.allocate_tensors()

        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        # Model input shape (e.g. 300x300)
        self.input_height = self.input_details[0]["shape"][1]
        self.input_width = self.input_details[0]["shape"][2]

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Run inference on a BGR frame.
        Returns a list of dicts: {label, confidence, bbox: [ymin, xmin, ymax, xmax]}
        with coordinates normalised 0-1.
        """
        # Prepare input
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.input_width, self.input_height))
        input_data = np.expand_dims(resized, axis=0).astype(np.uint8)

        self.interpreter.set_tensor(self.input_details[0]["index"], input_data)
        self.interpreter.invoke()

        # Parse outputs
        boxes = self.interpreter.get_tensor(self.output_details[0]["index"])[0]       # [N, 4]
        class_ids = self.interpreter.get_tensor(self.output_details[1]["index"])[0]   # [N]
        scores = self.interpreter.get_tensor(self.output_details[2]["index"])[0]      # [N]

        detections = []
        for i in range(len(scores)):
            if scores[i] < self.confidence_threshold:
                continue
            cid = int(class_ids[i])
            label = self.labels[cid] if cid < len(self.labels) else f"id:{cid}"
            detections.append({
                "label": label,
                "confidence": float(scores[i]),
                "bbox": boxes[i].tolist(),   # [ymin, xmin, ymax, xmax] normalised
            })

        return detections

    def draw(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Draw bounding boxes and labels onto the frame (in-place). Returns frame."""
        h, w = frame.shape[:2]

        for det in detections:
            ymin, xmin, ymax, xmax = det["bbox"]
            x1 = int(xmin * w)
            y1 = int(ymin * h)
            x2 = int(xmax * w)
            y2 = int(ymax * h)

            # Pick colour from palette based on label hash
            color = BOX_COLORS[hash(det["label"]) % len(BOX_COLORS)]
            thickness = 2

            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

            # Label background
            label_text = f"{det['label']} {det['confidence']:.0%}"
            (tw, th), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(frame, (x1, y1 - th - baseline - 6), (x1 + tw + 6, y1), color, -1)

            # Label text
            cv2.putText(
                frame, label_text,
                (x1 + 3, y1 - baseline - 3),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA,
            )

        return frame
