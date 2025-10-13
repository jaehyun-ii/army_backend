"""
Pydantic schemas for inference metadata validation.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class BoundingBox(BaseModel):
    """Bounding box coordinates."""
    x1: float = Field(..., ge=0, description="Top-left x coordinate")
    y1: float = Field(..., ge=0, description="Top-left y coordinate")
    x2: float = Field(..., ge=0, description="Bottom-right x coordinate")
    y2: float = Field(..., ge=0, description="Bottom-right y coordinate")

    @field_validator('x2')
    @classmethod
    def x2_must_be_greater_than_x1(cls, v, info):
        """Validate that x2 > x1."""
        if 'x1' in info.data and v <= info.data['x1']:
            raise ValueError('x2 must be greater than x1')
        return v

    @field_validator('y2')
    @classmethod
    def y2_must_be_greater_than_y1(cls, v, info):
        """Validate that y2 > y1."""
        if 'y1' in info.data and v <= info.data['y1']:
            raise ValueError('y2 must be greater than y1')
        return v


class Detection(BaseModel):
    """Single detection result."""
    class_: str = Field(..., alias="class", min_length=1, description="Class name")
    class_id: int = Field(..., ge=0, description="Class ID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")

    class Config:
        populate_by_name = True


class ImageMetadata(BaseModel):
    """Metadata for a single image."""
    filename: str = Field(..., min_length=1, description="Image filename")
    detections: List[Detection] = Field(default_factory=list, description="List of detections")

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        """Ensure filename is not empty and doesn't contain path traversal."""
        if '..' in v or v.startswith('/'):
            raise ValueError('Filename must not contain path traversal characters')
        return v


class InferenceMetadataJSON(BaseModel):
    """Complete inference metadata JSON structure."""
    model: str = Field(..., min_length=1, description="Model name/identifier")
    timestamp: str = Field(..., description="Inference timestamp (ISO format)")
    images: List[ImageMetadata] = Field(..., min_items=1, description="List of image metadata")

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v):
        """Validate ISO format timestamp."""
        from datetime import datetime
        try:
            # Try parsing with 'Z' suffix
            if v.endswith('Z'):
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            else:
                datetime.fromisoformat(v)
        except ValueError:
            raise ValueError(f'Invalid ISO timestamp format: {v}')
        return v

    @field_validator('images')
    @classmethod
    def validate_images_not_empty(cls, v):
        """Ensure at least one image is present."""
        if not v:
            raise ValueError('At least one image must be present in metadata')
        return v
