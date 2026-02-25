"""
API routes — Detection settings.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.capture import capture_manager

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)


class SettingsUpdate(BaseModel):
    confidence: float | None = Field(None, ge=0.01, le=1.0)
    slices: int | None = Field(None, ge=1, le=8)


@router.get("")
async def get_settings():
    """Return current detection settings."""
    return {
        "confidence": capture_manager.confidence,
        "slices": capture_manager.slices,
    }


@router.put("")
async def update_settings(body: SettingsUpdate):
    """Update detection settings."""
    updated = {}

    if body.confidence is not None:
        capture_manager.confidence = body.confidence
        updated["confidence"] = capture_manager.confidence

    if body.slices is not None:
        old_slices = capture_manager.slices
        capture_manager.slices = body.slices
        updated["slices"] = capture_manager.slices

    # Estimate processing time based on slice count for user warning
    estimated_seconds = capture_manager.slices ** 2 * 3  # rough: ~3s per slice on Pi 4
    warning = None
    if capture_manager.slices >= 4:
        warning = (
            f"With {capture_manager.slices}x{capture_manager.slices} slices "
            f"({capture_manager.slices ** 2} tiles), each capture may take "
            f"approximately {estimated_seconds} seconds to process."
        )

    logger.info("Settings updated: %s", updated)
    return {
        "status": "ok",
        "settings": {
            "confidence": capture_manager.confidence,
            "slices": capture_manager.slices,
        },
        "estimated_processing_seconds": estimated_seconds,
        "warning": warning,
    }
