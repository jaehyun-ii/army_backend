"""
Experiment schemas.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from app.models.experiment import ExperimentStatus


# Experiment
class ExperimentBase(BaseModel):
    """Base experiment schema."""

    name: str
    description: Optional[str] = None
    objective: Optional[str] = None
    hypothesis: Optional[str] = None
    tags: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None


class ExperimentCreate(ExperimentBase):
    """Schema for creating experiment."""

    pass


class ExperimentUpdate(BaseModel):
    """Schema for updating experiment."""

    name: Optional[str] = None
    description: Optional[str] = None
    objective: Optional[str] = None
    hypothesis: Optional[str] = None
    status: Optional[ExperimentStatus] = None
    tags: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    results_summary: Optional[Dict[str, Any]] = None


class ExperimentResponse(ExperimentBase):
    """Schema for experiment response."""

    id: UUID
    status: ExperimentStatus
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    results_summary: Optional[Dict[str, Any]]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
