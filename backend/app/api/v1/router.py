"""
API v1 router.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    storage,
    images,
    datasets_2d,
    dataset_service,
    realtime,
    models,
    evaluation,
    experiments,
    adversarial_patch,
    noise_attack,
    custom_models,
)

api_router = APIRouter()

# Include endpoint routers
# Authentication
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Storage
api_router.include_router(storage.router, prefix="/storage", tags=["Storage"])

# Images
api_router.include_router(images.router, prefix="/images", tags=["Images"])

# Dataset CRUD (database operations only)
api_router.include_router(datasets_2d.datasets_router, prefix="/datasets-2d", tags=["2D Datasets"])

# Dataset Service (upload, file management, business logic)
api_router.include_router(dataset_service.router, prefix="/dataset-service", tags=["Dataset Service"])

# Core endpoints
api_router.include_router(realtime.router, prefix="/realtime", tags=["Real-time Performance"])
api_router.include_router(models.router, prefix="/models", tags=["Models"])
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["Evaluation"])
api_router.include_router(experiments.router, prefix="/experiments", tags=["Experiments"])

# Adversarial Attacks
api_router.include_router(adversarial_patch.router, prefix="/adversarial-patch", tags=["Adversarial Patch"])
api_router.include_router(noise_attack.router, prefix="/noise-attack", tags=["Noise Attacks"])

# Custom Model Integration
api_router.include_router(custom_models.router, prefix="/custom-models", tags=["Custom Models"])
