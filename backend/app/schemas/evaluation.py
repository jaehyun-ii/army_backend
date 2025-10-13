"""
Pydantic schemas for evaluation endpoints.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from uuid import UUID
from enum import Enum


class EvalStatus(str, Enum):
    """Evaluation run status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class EvalPhase(str, Enum):
    """Evaluation phase."""
    PRE_ATTACK = "pre_attack"
    POST_ATTACK = "post_attack"


class DatasetDimension(str, Enum):
    """Dataset dimension."""
    TWO_D = "2d"
    THREE_D = "3d"


# ========== Evaluation Run Schemas ==========

class EvalRunBase(BaseModel):
    """Base schema for evaluation run."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    phase: EvalPhase
    model_version_id: UUID
    dataset_dimension: DatasetDimension = DatasetDimension.TWO_D
    # 2D datasets
    base_dataset_id: Optional[UUID] = None
    attack_dataset_id: Optional[UUID] = None
    # 3D datasets
    base_dataset_3d_id: Optional[UUID] = None
    attack_dataset_3d_id: Optional[UUID] = None
    # Experiment linkage
    experiment_id: Optional[UUID] = None
    params: Optional[Dict[str, Any]] = Field(None, description="Evaluation parameters (threshold, NMS, IoU, etc.)")


class EvalRunCreate(EvalRunBase):
    """Schema for creating evaluation run."""

    @field_validator("params")
    @classmethod
    def validate_params(cls, v):
        """Validate params is a dict if provided."""
        if v is not None and not isinstance(v, dict):
            raise ValueError("params must be a JSON object")
        return v


class EvalRunUpdate(BaseModel):
    """Schema for updating evaluation run."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[EvalStatus] = None
    metrics_summary: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    params: Optional[Dict[str, Any]] = None


class EvalRunResponse(EvalRunBase):
    """Schema for evaluation run response."""
    id: UUID
    status: EvalStatus
    metrics_summary: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EvalRunListResponse(BaseModel):
    """Schema for paginated evaluation run list."""
    items: List[EvalRunResponse]
    total: int
    page: int
    page_size: int


# ========== Evaluation Item Schemas ==========

class EvalItemBase(BaseModel):
    """Base schema for evaluation item."""
    run_id: UUID
    image_2d_id: Optional[UUID] = None
    image_3d_id: Optional[UUID] = None
    file_name: Optional[str] = Field(None, max_length=1024)
    storage_key: Optional[str] = None
    ground_truth: Optional[Union[Dict[str, Any], List[Any]]] = Field(None, description="GT bounding boxes/classes")
    prediction: Optional[Union[Dict[str, Any], List[Any]]] = Field(None, description="Model predictions")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Per-item metrics")
    notes: Optional[str] = None


class EvalItemCreate(EvalItemBase):
    """Schema for creating evaluation item."""
    pass


class EvalItemUpdate(BaseModel):
    """Schema for updating evaluation item."""
    ground_truth: Optional[Union[Dict[str, Any], List[Any]]] = None
    prediction: Optional[Union[Dict[str, Any], List[Any]]] = None
    metrics: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class EvalItemResponse(EvalItemBase):
    """Schema for evaluation item response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EvalItemListResponse(BaseModel):
    """Schema for paginated evaluation item list."""
    items: List[EvalItemResponse]
    total: int
    page: int
    page_size: int


# ========== Evaluation Class Metrics Schemas ==========

class EvalClassMetricsBase(BaseModel):
    """Base schema for evaluation class metrics."""
    run_id: UUID
    class_name: str = Field(..., min_length=1, max_length=200)
    metrics: Dict[str, Any] = Field(..., description="Per-class metrics (AP, precision, recall, etc.)")


class EvalClassMetricsCreate(EvalClassMetricsBase):
    """Schema for creating evaluation class metrics."""

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, v):
        """Validate metrics is a dict."""
        if not isinstance(v, dict):
            raise ValueError("metrics must be a JSON object")
        return v


class EvalClassMetricsUpdate(BaseModel):
    """Schema for updating evaluation class metrics."""
    metrics: Dict[str, Any]


class EvalClassMetricsResponse(EvalClassMetricsBase):
    """Schema for evaluation class metrics response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EvalClassMetricsListResponse(BaseModel):
    """Schema for evaluation class metrics list."""
    items: List[EvalClassMetricsResponse]
    total: int


# ========== Evaluation List Schemas ==========

class EvalListBase(BaseModel):
    """Base schema for evaluation list."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class EvalListCreate(EvalListBase):
    """Schema for creating evaluation list."""
    pass


class EvalListUpdate(BaseModel):
    """Schema for updating evaluation list."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None


class EvalListResponse(EvalListBase):
    """Schema for evaluation list response."""
    id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EvalListWithItemsResponse(EvalListResponse):
    """Schema for evaluation list with items."""
    items: List["EvalListItemResponse"]


class EvalListListResponse(BaseModel):
    """Schema for paginated evaluation list."""
    items: List[EvalListResponse]
    total: int
    page: int
    page_size: int


# ========== Evaluation List Item Schemas ==========

class EvalListItemBase(BaseModel):
    """Base schema for evaluation list item."""
    list_id: UUID
    run_id: UUID
    sort_order: int = 0


class EvalListItemCreate(EvalListItemBase):
    """Schema for creating evaluation list item."""
    pass


class EvalListItemUpdate(BaseModel):
    """Schema for updating evaluation list item."""
    sort_order: Optional[int] = None


class EvalListItemResponse(EvalListItemBase):
    """Schema for evaluation list item response."""
    id: UUID
    created_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ========== Comparison Schemas ==========

class EvalRunPairResponse(BaseModel):
    """Schema for pre/post evaluation run pair comparison."""
    pre_run_id: UUID
    post_run_id: UUID
    model_version_id: UUID
    base_dataset_id: UUID
    attack_dataset_id: UUID
    pre_metrics: Optional[Dict[str, Any]] = None
    post_metrics: Optional[Dict[str, Any]] = None
    pre_created_at: datetime
    post_created_at: datetime


class EvalRunPairDeltaResponse(EvalRunPairResponse):
    """Schema for pre/post evaluation run pair with delta metrics."""
    pre_map: Optional[float] = None
    post_map: Optional[float] = None
    delta_map: Optional[float] = None


class EvalRunComparisonResponse(BaseModel):
    """Schema for detailed evaluation run comparison."""
    pre_run: EvalRunResponse
    post_run: EvalRunResponse
    delta_metrics: Dict[str, Any] = Field(default_factory=dict, description="Computed metric deltas")
