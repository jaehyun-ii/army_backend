"""
Real-time performance measurement schemas.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal

from app.models.realtime import RTRunStatus


# Camera
class CameraBase(BaseModel):
    """Base camera schema."""

    name: str
    description: Optional[str] = None
    stream_uri: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    resolution: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True


class CameraCreate(CameraBase):
    """Schema for creating camera."""

    pass


class CameraUpdate(BaseModel):
    """Schema for updating camera."""

    name: Optional[str] = None
    description: Optional[str] = None
    stream_uri: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    resolution: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class CameraResponse(BaseModel):
    """Schema for camera response."""

    id: UUID
    name: str
    description: Optional[str] = None
    stream_uri: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    resolution: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, validation_alias="metadata_")
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# RT Capture Run
class RTCaptureRunBase(BaseModel):
    """Base RT capture run schema."""

    window_seconds: int = 5
    frames_expected: int = 10
    fps_target: Optional[Decimal] = None
    notes: Optional[str] = None


class RTCaptureRunCreate(RTCaptureRunBase):
    """Schema for creating RT capture run."""

    camera_id: UUID
    detect_model_version_id: UUID


class RTCaptureRunUpdate(BaseModel):
    """Schema for updating RT capture run."""

    ended_at: Optional[datetime] = None
    status: Optional[RTRunStatus] = None
    notes: Optional[str] = None


class RTCaptureRunResponse(RTCaptureRunBase):
    """Schema for RT capture run response."""

    id: UUID
    camera_id: UUID
    detect_model_version_id: UUID
    started_at: datetime
    ended_at: Optional[datetime]
    status: RTRunStatus
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# RT Frame
class RTFrameBase(BaseModel):
    """Base RT frame schema."""

    seq_no: int
    storage_key: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, validation_alias="metadata_")


class RTFrameCreate(RTFrameBase):
    """Schema for creating RT frame."""

    run_id: UUID
    captured_at: Optional[datetime] = None


class RTFrameUpdate(BaseModel):
    """Schema for updating RT frame."""

    storage_key: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RTFrameResponse(RTFrameBase):
    """Schema for RT frame response."""

    id: UUID
    run_id: UUID
    captured_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# RT Inference
class RTInferenceBase(BaseModel):
    """Base RT inference schema."""

    latency_ms: Optional[int] = None
    inference: Dict[str, Any]
    stats: Optional[Dict[str, Any]] = None


class RTInferenceCreate(RTInferenceBase):
    """Schema for creating RT inference."""

    frame_id: UUID
    detect_model_version_id: UUID


class RTInferenceUpdate(BaseModel):
    """Schema for updating RT inference."""

    latency_ms: Optional[int] = None
    stats: Optional[Dict[str, Any]] = None


class RTInferenceResponse(RTInferenceBase):
    """Schema for RT inference response."""

    id: UUID
    frame_id: UUID
    detect_model_version_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
