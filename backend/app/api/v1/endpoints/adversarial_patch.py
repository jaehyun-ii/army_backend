"""
Adversarial patch generation and attack dataset creation endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from uuid import UUID
from pydantic import Field
from pathlib import Path

from app.database import get_db
from app import schemas, crud
from app.services.adversarial_patch_service import adversarial_patch_service
from app.services.attack_support import AttackSSEManager

router = APIRouter()
sse_manager = AttackSSEManager()


@router.post("/patches/generate", status_code=status.HTTP_201_CREATED)
async def generate_adversarial_patch(
    *,
    db: AsyncSession = Depends(get_db),
    request: schemas.PatchGenerationRequest
) -> Dict[str, Any]:
    """
    Generate adversarial patch using specified plugin.

    This endpoint:
    1. Loads the target model
    2. Runs inference on dataset to find target class instances
    3. Generates a universal adversarial patch using specified plugin
    4. Saves the patch and creates a database record

    Parameters:
        - patch_name: Name for the generated patch
        - model_version_id: ID of the model to attack
        - dataset_id: ID of the dataset containing training images
        - target_class: Class name to attack (e.g., "person", "car", "dog")
        - plugin_name: Patch generation plugin to use (default: "global_pgd_2d")
        - patch_size: Base size of the patch (default: 100)
        - area_ratio: Patch area as ratio of bbox area (default: 0.3)
        - epsilon: Max perturbation (default: 0.6)
        - alpha: Learning rate (default: 0.03)
        - iterations: Training iterations (default: 100)
        - batch_size: Batch size for training (default: 8)

    Returns:
        - patch: Patch database record
        - patch_file: Path to saved patch image
        - statistics: Generation statistics
    """
    try:
        patch_db, patch_path = await adversarial_patch_service.generate_patch(
            db=db,
            patch_name=request.patch_name,
            model_version_id=request.model_version_id,
            dataset_id=request.dataset_id,
            target_class=request.target_class,
            plugin_name=request.plugin_name,
            patch_size=request.patch_size,
            area_ratio=request.area_ratio,
            epsilon=request.epsilon,
            alpha=request.alpha,
            iterations=request.iterations,
            batch_size=request.batch_size,
            description=request.description,
            created_by=request.created_by,
            sse_manager=sse_manager,
            session_id=request.session_id
        )

        return {
            "patch": schemas.Patch2DResponse.model_validate(patch_db),
            "patch_file": str(patch_path),
            "statistics": {
                "num_training_samples": patch_db.patch_metadata.get("num_training_samples", 0),
                "target_class": request.target_class,
                "target_class_id": patch_db.patch_metadata.get("target_class_id"),
                "best_score": patch_db.patch_metadata.get("best_score")
            },
            "message": f"Successfully generated adversarial patch '{request.patch_name}'"
        }

    except ValueError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Validation error in patch generation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating patch: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating patch: {str(e)}"
        )


@router.get("/patches/{patch_id}", response_model=schemas.Patch2DResponse)
async def get_patch(
    patch_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> schemas.Patch2DResponse:
    """Get patch details by ID."""
    patch = await crud.patch_2d.get(db, id=patch_id)
    if not patch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patch with ID {patch_id} not found"
        )
    return patch


@router.get("/patches/{patch_id}/image")
async def get_patch_image(
    patch_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get adversarial patch image for preview.

    Args:
        patch_id: Patch ID

    Returns:
        PNG image (inline display)
    """
    try:
        patch = await crud.patch_2d.get(db, id=patch_id)
        if not patch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patch {patch_id} not found"
            )

        patch_file = patch.patch_metadata.get("patch_file")
        if not patch_file or not Path(patch_file).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patch file not found"
            )

        return FileResponse(
            path=patch_file,
            media_type="image/png",
            headers={"Content-Disposition": "inline"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving patch image: {str(e)}"
        )


@router.get("/patches/{patch_id}/download")
async def download_patch(
    patch_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Download adversarial patch file.

    Args:
        patch_id: Patch ID to download

    Returns:
        PNG file of the adversarial patch (as download)
    """
    try:
        patch = await crud.patch_2d.get(db, id=patch_id)
        if not patch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patch {patch_id} not found"
            )

        patch_file = patch.patch_metadata.get("patch_file")
        if not patch_file or not Path(patch_file).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patch file not found"
            )

        return FileResponse(
            path=patch_file,
            media_type="image/png",
            filename=f"{patch.name}.png",
            headers={"Content-Disposition": f"attachment; filename={patch.name}.png"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading patch: {str(e)}"
        )


@router.post("/attack-datasets/generate", status_code=status.HTTP_201_CREATED)
async def generate_attack_dataset(
    *,
    db: AsyncSession = Depends(get_db),
    attack_dataset_name: str = Body(..., description="Name for attack dataset"),
    detect_model_version_id: UUID = Body(..., description="Model version ID"),
    base_dataset_id: UUID = Body(..., description="Base dataset ID"),
    patch_id: UUID = Body(..., description="Patch ID to apply"),
    target_class: str = Body(..., description="Target class to apply patch to"),
    patch_scale: float = Body(0.3, ge=0.05, le=1.0, description="Patch scale ratio (0.05-1.0)"),
    description: Optional[str] = Body(None, description="Optional description"),
    created_by: Optional[UUID] = Body(None, description="Optional creator ID")
) -> Dict[str, Any]:
    """
    Generate adversarial attack dataset by applying patch to images.

    This endpoint:
    1. Loads the patch and base dataset
    2. Runs inference to find target class instances
    3. Applies patch to center of each target class bbox
    4. Saves attacked images to new dataset
    5. Creates attack dataset record

    Parameters:
        - attack_dataset_name: Name for the attack dataset
        - model_version_id: Model version ID for inference
        - base_dataset_id: Base dataset to apply patches to
        - patch_id: ID of the patch to apply
        - target_class: Target class name to apply patch to
        - patch_scale: Scale of patch relative to bbox area (0.05-1.0)

    Returns:
        - attack_dataset: Attack dataset database record
        - storage_path: Path to attacked images
        - statistics: Attack statistics
    """
    try:
        attack_db, attack_dir = await adversarial_patch_service.apply_patch_to_dataset(
            db=db,
            attack_dataset_name=attack_dataset_name,
            model_version_id=model_version_id,
            base_dataset_id=base_dataset_id,
            patch_id=patch_id,
            target_class=target_class,
            patch_scale=patch_scale,
            description=description,
            created_by=created_by
        )

        processed_images = attack_db.parameters.get("processed_images", 0)

        return {
            "attack_dataset": schemas.AttackDataset2DResponse.model_validate(attack_db),
            "storage_path": str(attack_dir),
            "statistics": {
                "processed_images": processed_images,
                "target_class": target_class,
                "patch_scale": patch_scale
            },
            "message": f"Successfully created attack dataset with {processed_images} images"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating attack dataset: {str(e)}"
        )


@router.get("/attack-datasets/{attack_id}/download")
async def download_attack_dataset(
    attack_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Download attack dataset as ZIP file.

    Args:
        attack_id: Attack dataset ID to download

    Returns:
        ZIP file containing all attacked images and metadata
    """
    try:
        attack = await crud.attack_dataset_2d.get(db, id=attack_id)
        if not attack:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attack dataset {attack_id} not found"
            )

        try:
            archive_path = adversarial_patch_service.prepare_attack_dataset_archive(
                attack
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc)
            ) from exc

        background = BackgroundTask(
            adversarial_patch_service.cleanup_attack_dataset_archive,
            archive_path
        )

        return FileResponse(
            path=str(archive_path),
            media_type="application/zip",
            filename=f"{attack.name}.zip",
            background=background
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading attack dataset: {str(e)}"
        )


@router.get("/attack-datasets/{attack_id}", response_model=schemas.AttackDataset2DResponse)
async def get_attack_dataset(
    attack_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> schemas.AttackDataset2DResponse:
    """
    Get attack dataset details by ID.

    Args:
        attack_id: Attack dataset ID

    Returns:
        Attack dataset record
    """
    attack = await crud.attack_dataset_2d.get(db, id=attack_id)
    if not attack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attack dataset {attack_id} not found"
        )
    return attack


@router.get("/patches", response_model=List[schemas.Patch2DResponse])
async def list_patches(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    target_class: Optional[str] = Query(None, description="Filter by target class")
):
    """
    List adversarial patches with optional filtering.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        target_class: Optional filter by target class

    Returns:
        List of patch records
    """
    if target_class:
        # Filter by target class
        patches = await crud.patch_2d.get_multi(db, skip=skip, limit=limit)
        patches = [p for p in patches if p.target_class == target_class]
    else:
        patches = await crud.patch_2d.get_multi(db, skip=skip, limit=limit)

    return patches


@router.get("/attack-datasets", response_model=List[schemas.AttackDataset2DResponse])
async def list_attack_datasets(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    target_class: Optional[str] = Query(None, description="Filter by target class")
):
    """
    List attack datasets with optional filtering.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        target_class: Optional filter by target class

    Returns:
        List of attack dataset records
    """
    if target_class:
        # Filter by target class
        attacks = await crud.attack_dataset_2d.get_multi(db, skip=skip, limit=limit)
        attacks = [a for a in attacks if a.target_class == target_class]
    else:
        attacks = await crud.attack_dataset_2d.get_multi(db, skip=skip, limit=limit)

    return attacks


@router.get("/patches/{session_id}/events")
async def patch_generation_events(session_id: str):
    """
    SSE endpoint for real-time patch generation logs.

    Connect before calling /patches/generate with the same session_id.
    Receives:
    - Progress updates (iteration, loss, epoch)
    - Status changes (loading_data, training, saving)
    - Completion notification
    - Error messages

    Example event format:
    data: {"type": "progress", "message": "Processing...", "timestamp": "..."}
    """
    # Create session for this SSE connection
    sse_manager.create_session(session_id)

    return StreamingResponse(
        sse_manager.event_stream(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
