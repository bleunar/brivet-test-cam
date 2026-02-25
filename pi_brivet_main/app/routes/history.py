"""
API routes — Detection history.
"""

import os
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import CAPTURES_DIR
from app.database import get_db
from app.models import Detection

router = APIRouter(prefix="/api/history", tags=["history"])
logger = logging.getLogger(__name__)


@router.get("")
async def list_detections(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return paginated detection history (newest first)."""
    total = db.query(Detection).count()
    detections = (
        db.query(Detection)
        .order_by(Detection.timestamp.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, -(-total // per_page)),  # ceil division
        "data": [d.to_dict() for d in detections],
    }


@router.get("/{detection_id}")
async def get_detection(detection_id: int, db: Session = Depends(get_db)):
    """Return a single detection record."""
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if not detection:
        return {"status": "error", "message": "Detection not found."}
    return {"status": "ok", "data": detection.to_dict()}


@router.get("/{detection_id}/image")
async def get_detection_image(detection_id: int, db: Session = Depends(get_db)):
    """Serve the annotated detection image."""
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if not detection:
        return {"status": "error", "message": "Detection not found."}

    filepath = CAPTURES_DIR / detection.image_filename
    if not filepath.exists():
        return {"status": "error", "message": "Image file not found."}

    return FileResponse(str(filepath), media_type="image/jpeg")


@router.delete("/{detection_id}")
async def delete_detection(detection_id: int, db: Session = Depends(get_db)):
    """Delete a detection record and its associated image."""
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if not detection:
        return {"status": "error", "message": "Detection not found."}

    # Delete image file
    filepath = CAPTURES_DIR / detection.image_filename
    try:
        if filepath.exists():
            os.remove(filepath)
    except OSError:
        logger.warning("Could not delete image file: %s", filepath)

    db.delete(detection)
    db.commit()
    return {"status": "ok", "message": "Detection deleted."}
