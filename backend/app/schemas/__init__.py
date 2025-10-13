"""
Pydantic schemas for request/response validation.
"""
from app.schemas.user import UserCreate, UserUpdate, UserResponse, Token, TokenData
from app.schemas.dataset_2d import (
    Dataset2DCreate,
    Dataset2DUpdate,
    Dataset2DResponse,
    DatasetSummaryResponse,
    DatasetStatisticsResponse,
    ImageCreate,
    ImageResponse,
    Patch2DCreate,
    Patch2DResponse,
    PatchGenerationRequest,
    AttackDataset2DCreate,
    AttackDataset2DResponse,
)
from app.schemas.model_repo import (
    ODModelCreate,
    ODModelResponse,
    ODModelVersionCreate,
    ODModelVersionResponse,
    ODModelArtifactCreate,
    ODModelArtifactResponse,
)
from app.schemas.realtime import (
    CameraCreate,
    CameraUpdate,
    CameraResponse,
    RTCaptureRunCreate,
    RTCaptureRunUpdate,
    RTCaptureRunResponse,
    RTFrameCreate,
    RTFrameUpdate,
    RTFrameResponse,
    RTInferenceCreate,
    RTInferenceUpdate,
    RTInferenceResponse,
)
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
)
from app.schemas.evaluation import (
    EvalRunCreate,
    EvalRunUpdate,
    EvalRunResponse,
    EvalItemCreate,
    EvalItemUpdate,
    EvalItemResponse,
    EvalClassMetricsCreate,
    EvalClassMetricsUpdate,
    EvalClassMetricsResponse,
)

__all__ = [
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "Token",
    "TokenData",
    # 2D Datasets
    "Dataset2DCreate",
    "Dataset2DUpdate",
    "Dataset2DResponse",
    "DatasetSummaryResponse",
    "DatasetStatisticsResponse",
    "ImageCreate",
    "ImageResponse",
    "Patch2DCreate",
    "Patch2DResponse",
    "PatchGenerationRequest",
    "AttackDataset2DCreate",
    "AttackDataset2DResponse",
    # Model Repo
    "ODModelCreate",
    "ODModelResponse",
    "ODModelVersionCreate",
    "ODModelVersionResponse",
    "ODModelArtifactCreate",
    "ODModelArtifactResponse",
    # Real-time Performance
    "CameraCreate",
    "CameraUpdate",
    "CameraResponse",
    "RTCaptureRunCreate",
    "RTCaptureRunUpdate",
    "RTCaptureRunResponse",
    "RTFrameCreate",
    "RTFrameUpdate",
    "RTFrameResponse",
    "RTInferenceCreate",
    "RTInferenceUpdate",
    "RTInferenceResponse",
    # Experiments
    "ExperimentCreate",
    "ExperimentUpdate",
    "ExperimentResponse",
    # Evaluations
    "EvalRunCreate",
    "EvalRunUpdate",
    "EvalRunResponse",
    "EvalItemCreate",
    "EvalItemUpdate",
    "EvalItemResponse",
    "EvalClassMetricsCreate",
    "EvalClassMetricsUpdate",
    "EvalClassMetricsResponse",
]
