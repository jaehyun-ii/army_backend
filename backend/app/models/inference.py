"""
Inference metadata models for YOLO detection results.
"""
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, TIMESTAMP, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class InferenceMetadata(Base):
    """Inference metadata for dataset."""

    __tablename__ = "inference_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datasets_2d.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Inference info
    model_name = Column(String(100), nullable=False)
    inference_timestamp = Column(TIMESTAMP, nullable=False)

    # Statistics (cached)
    total_images = Column(Integer, nullable=False, default=0)
    total_detections = Column(Integer, nullable=False, default=0)

    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    detections = relationship("ImageDetection", back_populates="inference_metadata", cascade="all, delete-orphan")
    dataset = relationship("Dataset2D", back_populates="inference_metadata")


class ImageDetection(Base):
    """Individual detection result."""

    __tablename__ = "image_detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_id = Column(
        UUID(as_uuid=True),
        ForeignKey("images_2d.id", ondelete="CASCADE"),
        nullable=False
    )
    inference_metadata_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inference_metadata.id", ondelete="CASCADE"),
        nullable=False
    )

    # Detection info
    class_name = Column(String(50), nullable=False, index=True)
    class_id = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False, index=True)

    # Bounding box
    bbox_x1 = Column(Float, nullable=False)
    bbox_y1 = Column(Float, nullable=False)
    bbox_x2 = Column(Float, nullable=False)
    bbox_y2 = Column(Float, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    image = relationship("Image2D", back_populates="detections")
    inference_metadata = relationship("InferenceMetadata", back_populates="detections")


class DatasetClassStatistics(Base):
    """Aggregated class statistics per dataset."""

    __tablename__ = "dataset_class_statistics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datasets_2d.id", ondelete="CASCADE"),
        nullable=False
    )

    # Class info
    class_name = Column(String(50), nullable=False)
    class_id = Column(Integer, nullable=False)

    # Statistics
    detection_count = Column(Integer, nullable=False, default=0)
    image_count = Column(Integer, nullable=False, default=0)
    avg_confidence = Column(Float, nullable=False)
    min_confidence = Column(Float, nullable=False)
    max_confidence = Column(Float, nullable=False)

    # Metadata
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    dataset = relationship("Dataset2D", back_populates="class_statistics")

    # Unique constraint and indexes
    __table_args__ = (
        UniqueConstraint('dataset_id', 'class_name', name='uq_dataset_class'),
        Index('idx_class_stats_count', 'dataset_id', 'detection_count'),
    )
