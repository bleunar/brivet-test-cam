"""
SQLAlchemy ORM models.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, Float, String, DateTime

from app.database import Base


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    object_count = Column(Integer, nullable=False, default=0)
    confidence_threshold = Column(Float, nullable=False)
    slice_count = Column(Integer, nullable=False)
    image_filename = Column(String, nullable=False)

    # Future: GPS integration
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "object_count": self.object_count,
            "confidence_threshold": self.confidence_threshold,
            "slice_count": self.slice_count,
            "image_filename": self.image_filename,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }
