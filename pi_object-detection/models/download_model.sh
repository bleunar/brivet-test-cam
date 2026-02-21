#!/usr/bin/env bash
# Download the pre-trained MobileNet SSD v1 (COCO) TFLite model and labels.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL_URL="https://storage.googleapis.com/download.tensorflow.org/models/tflite/coco_ssd_mobilenet_v1_1.0_quant_2018_06_29.zip"
ZIP_FILE="${SCRIPT_DIR}/model.zip"

echo "Downloading MobileNet SSD v1 (COCO) TFLite model..."
curl -L -o "${ZIP_FILE}" "${MODEL_URL}"

echo "Extracting..."
unzip -o "${ZIP_FILE}" -d "${SCRIPT_DIR}"

# Rename to consistent names
mv -f "${SCRIPT_DIR}/detect.tflite" "${SCRIPT_DIR}/detect.tflite" 2>/dev/null || true
mv -f "${SCRIPT_DIR}/labelmap.txt" "${SCRIPT_DIR}/labelmap.txt" 2>/dev/null || true

# Cleanup
rm -f "${ZIP_FILE}"

echo "Done! Model files:"
ls -lh "${SCRIPT_DIR}/detect.tflite" "${SCRIPT_DIR}/labelmap.txt"
