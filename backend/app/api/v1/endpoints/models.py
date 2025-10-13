"""
Model repository endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.database import get_db
from app import crud, schemas

router = APIRouter()


# Model Versions (must be before /{model_id} to avoid path conflicts)
@router.post("/versions", response_model=schemas.ODModelVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_model_version(
    *,
    db: AsyncSession = Depends(get_db),
    version_in: schemas.ODModelVersionCreate,
) -> schemas.ODModelVersionResponse:
    """Create a new model version."""
    version = await crud.od_model_version.create(db, obj_in=version_in)
    return version


@router.get("/versions")
async def list_model_versions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List all model versions with model information."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.models.model_repo import ODModelVersion, ODModel

    result = await db.execute(
        select(ODModelVersion)
        .options(joinedload(ODModelVersion.model))
        .filter(ODModelVersion.deleted_at.is_(None))
        .offset(skip)
        .limit(limit)
    )
    versions = result.unique().scalars().all()

    # Format response with model name
    return [
        {
            "id": str(v.id),
            "model_id": str(v.model_id),
            "name": v.model.name if v.model else "Unknown",
            "version": v.version,
            "framework": v.framework,
            "stage": v.stage,
            "created_at": v.created_at.isoformat()
        }
        for v in versions
    ]


@router.get("/versions/{version_id}", response_model=schemas.ODModelVersionResponse)
async def get_model_version(
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> schemas.ODModelVersionResponse:
    """Get a model version by ID."""
    version = await crud.od_model_version.get(db, id=version_id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model version with ID {version_id} not found",
        )
    return version


# OD Models
@router.post("/", response_model=schemas.ODModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    *,
    db: AsyncSession = Depends(get_db),
    model_in: schemas.ODModelCreate,
) -> schemas.ODModelResponse:
    """Create a new OD model."""
    model = await crud.od_model.create(db, obj_in=model_in)
    return model


@router.get("/", response_model=List[schemas.ODModelResponse])
async def list_models(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> List[schemas.ODModelResponse]:
    """List OD models."""
    models = await crud.od_model.get_multi(db, skip=skip, limit=limit)
    return models


@router.get("/{model_id}", response_model=schemas.ODModelResponse)
async def get_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> schemas.ODModelResponse:
    """Get an OD model by ID."""
    model = await crud.od_model.get(db, id=model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )
    return model


# Model Artifacts
@router.post("/artifacts", response_model=schemas.ODModelArtifactResponse, status_code=status.HTTP_201_CREATED)
async def create_model_artifact(
    *,
    db: AsyncSession = Depends(get_db),
    artifact_in: schemas.ODModelArtifactCreate,
) -> schemas.ODModelArtifactResponse:
    """Create a new model artifact."""
    artifact = await crud.od_model_artifact.create(db, obj_in=artifact_in)
    return artifact
