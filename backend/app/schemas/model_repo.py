"""
Model repository schemas.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from app.models.model_repo import ModelFramework, ModelStage, ArtifactType


# OD Model
class ODModelBase(BaseModel):
    """Base OD model schema."""

    name: str
    task: str = "object-detection"
    description: Optional[str] = None


class ODModelCreate(ODModelBase):
    """Schema for creating OD model."""

    pass


class ODModelResponse(ODModelBase):
    """Schema for OD model response."""

    id: UUID
    owner_id: Optional[UUID]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# OD Model Version
class ODModelVersionBase(BaseModel):
    """Base OD model version schema."""

    version: str
    framework: ModelFramework
    framework_version: Optional[str] = None
    input_spec: Optional[Dict[str, Any]] = None
    training_metadata: Optional[Dict[str, Any]] = None
    labelmap: Optional[Dict[str, Any]] = None
    inference_params: Optional[Dict[str, Any]] = None
    stage: ModelStage = ModelStage.DRAFT


class ODModelVersionCreate(ODModelVersionBase):
    """Schema for creating OD model version."""

    detect_model_id: UUID


class ODModelVersionResponse(ODModelVersionBase):
    """Schema for OD model version response."""

    id: UUID
    detect_model_id: UUID
    created_by: Optional[UUID]
    published_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# OD Model Artifact
class ODModelArtifactBase(BaseModel):
    """Base OD model artifact schema."""

    artifact_type: ArtifactType
    storage_key: str
    file_name: str
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    content_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ODModelArtifactCreate(ODModelArtifactBase):
    """Schema for creating OD model artifact."""

    detect_model_version_id: UUID


class ODModelArtifactResponse(ODModelArtifactBase):
    """Schema for OD model artifact response."""

    id: UUID
    detect_model_version_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
