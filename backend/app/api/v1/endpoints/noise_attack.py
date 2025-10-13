"""
Noise-based adversarial attack endpoints (FGSM, PGD, Gaussian, Uniform).
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from uuid import UUID
import shutil
import tempfile
import asyncio
from pathlib import Path

from app.database import get_db
from app import schemas
from app.services.noise_attack_service import noise_attack_service
from app.services.attack_support import AttackSSEManager

router = APIRouter()

# Shared SSE Manager for real-time logging
sse_manager = AttackSSEManager()


@router.post("/fgsm/generate", status_code=status.HTTP_201_CREATED)
async def generate_fgsm_attack_dataset(
    *,
    db: AsyncSession = Depends(get_db),
    attack_dataset_name: str = Body(..., description="Name for attack dataset"),
    model_version_id: UUID = Body(..., description="Model version ID"),
    base_dataset_id: UUID = Body(..., description="Base dataset ID"),
    epsilon: float = Body(8.0, ge=0.1, le=255.0, description="Perturbation magnitude (0-255)"),
    targeted: bool = Body(False, description="Whether to use targeted attack"),
    target_class: Optional[str] = Body(None, description="Target class (for targeted attack)"),
    description: Optional[str] = Body(None, description="Optional description"),
    created_by: Optional[UUID] = Body(None, description="Optional creator ID"),
    session_id: Optional[str] = Body(None, description="SSE session ID for real-time logging")
) -> Dict[str, Any]:
    """
    Generate FGSM (Fast Gradient Sign Method) attack dataset.

    FGSM is a fast one-step attack that perturbs images in the direction
    of the gradient to fool the model.

    Parameters:
        - attack_dataset_name: Name for the attack dataset
        - model_version_id: Model to attack
        - base_dataset_id: Base dataset to attack
        - epsilon: Perturbation magnitude (0-255 scale, default: 8.0)
        - targeted: Use targeted attack (default: False)
        - target_class: Target class name for targeted attack

    Returns:
        - attack_dataset: Attack dataset record
        - storage_path: Path to attacked images
        - statistics: Attack statistics
    """
    try:
        if targeted and not target_class:
            raise ValueError("target_class is required for targeted attack")

        attack_db, attack_dir = await noise_attack_service.generate_noise_attack_dataset(
            db=db,
            attack_name=attack_dataset_name,
            base_dataset_id=base_dataset_id,
            plugin_name="fgsm_2d",
            model_version_id=model_version_id,
            epsilon=epsilon,
            targeted=targeted,
            target_class=target_class,
            description=description,
            created_by=created_by,
            session_id=session_id,
            sse_manager=sse_manager
        )

        processed_images = attack_db.parameters.get("processed_images", 0)

        return {
            "attack_dataset": schemas.AttackDataset2DResponse.model_validate(attack_db),
            "storage_path": str(attack_dir),
            "statistics": {
                "method": "FGSM",
                "processed_images": processed_images,
                "epsilon": epsilon,
                "targeted": targeted,
                "target_class": target_class
            },
            "message": f"Successfully created FGSM attack dataset with {processed_images} images"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating FGSM attack: {str(e)}"
        )


@router.post("/pgd/generate", status_code=status.HTTP_201_CREATED)
async def generate_pgd_attack_dataset(
    *,
    db: AsyncSession = Depends(get_db),
    attack_dataset_name: str = Body(..., description="Name for attack dataset"),
    model_version_id: UUID = Body(..., description="Model version ID"),
    base_dataset_id: UUID = Body(..., description="Base dataset ID"),
    epsilon: float = Body(8.0, ge=0.1, le=255.0, description="Max perturbation magnitude"),
    alpha: float = Body(2.0, ge=0.01, le=50.0, description="Step size"),
    iterations: int = Body(10, ge=1, le=100, description="Number of iterations"),
    targeted: bool = Body(False, description="Whether to use targeted attack"),
    target_class: Optional[str] = Body(None, description="Target class (for targeted attack)"),
    description: Optional[str] = Body(None, description="Optional description"),
    created_by: Optional[UUID] = Body(None, description="Optional creator ID"),
    session_id: Optional[str] = Body(None, description="SSE session ID for real-time logging")
) -> Dict[str, Any]:
    """
    Generate PGD (Projected Gradient Descent) attack dataset.

    PGD is an iterative attack that applies multiple gradient steps
    and projects the perturbation back to the epsilon ball.

    Parameters:
        - attack_dataset_name: Name for the attack dataset
        - model_version_id: Model to attack
        - base_dataset_id: Base dataset to attack
        - epsilon: Max perturbation magnitude (0-255 scale, default: 8.0)
        - alpha: Step size (default: 2.0)
        - iterations: Number of iterations (default: 10)
        - targeted: Use targeted attack (default: False)
        - target_class: Target class name for targeted attack

    Returns:
        - attack_dataset: Attack dataset record
        - storage_path: Path to attacked images
        - statistics: Attack statistics
    """
    try:
        if targeted and not target_class:
            raise ValueError("target_class is required for targeted attack")

        attack_db, attack_dir = await noise_attack_service.generate_noise_attack_dataset(
            db=db,
            attack_name=attack_dataset_name,
            base_dataset_id=base_dataset_id,
            plugin_name="pgd_2d",
            model_version_id=model_version_id,
            epsilon=epsilon,
            alpha=alpha,
            iterations=iterations,
            targeted=targeted,
            target_class=target_class,
            description=description,
            created_by=created_by,
            session_id=session_id,
            sse_manager=sse_manager
        )

        processed_images = attack_db.parameters.get("processed_images", 0)

        return {
            "attack_dataset": schemas.AttackDataset2DResponse.model_validate(attack_db),
            "storage_path": str(attack_dir),
            "statistics": {
                "method": "PGD",
                "processed_images": processed_images,
                "epsilon": epsilon,
                "alpha": alpha,
                "iterations": iterations,
                "targeted": targeted,
                "target_class": target_class
            },
            "message": f"Successfully created PGD attack dataset with {processed_images} images"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating PGD attack: {str(e)}"
        )


@router.post("/gaussian/generate", status_code=status.HTTP_201_CREATED)
async def generate_gaussian_noise_dataset(
    *,
    db: AsyncSession = Depends(get_db),
    attack_dataset_name: str = Body(..., description="Name for attack dataset"),
    base_dataset_id: UUID = Body(..., description="Base dataset ID"),
    mean: float = Body(0.0, description="Mean of Gaussian noise"),
    std: float = Body(25.0, ge=0.1, le=100.0, description="Standard deviation"),
    target_class: str = Body(..., description="Target class (noise applied inside bboxes)"),
    description: Optional[str] = Body(None, description="Optional description"),
    created_by: Optional[UUID] = Body(None, description="Optional creator ID"),
    session_id: Optional[str] = Body(None, description="SSE session ID for real-time logging")
) -> Dict[str, Any]:
    """
    Generate Gaussian noise attack dataset (targeted).

    Adds random Gaussian noise to images inside bounding boxes of target class.

    Parameters:
        - attack_dataset_name: Name for the attack dataset
        - base_dataset_id: Base dataset to add noise to
        - mean: Mean of Gaussian noise (default: 0.0)
        - std: Standard deviation (default: 25.0)
        - target_class: Target class name (noise only applied inside bboxes of this class)

    Returns:
        - attack_dataset: Attack dataset record
        - storage_path: Path to noisy images
        - statistics: Attack statistics
    """
    try:
        attack_db, attack_dir = await noise_attack_service.generate_noise_attack_dataset(
            db=db,
            attack_name=attack_dataset_name,
            base_dataset_id=base_dataset_id,
            plugin_name="gaussian_2d",
            mean=mean,
            std=std,
            target_class=target_class,
            targeted=True,
            description=description,
            created_by=created_by,
            session_id=session_id,
            sse_manager=sse_manager
        )

        processed_images = attack_db.parameters.get("processed_images", 0)

        return {
            "attack_dataset": schemas.AttackDataset2DResponse.model_validate(attack_db),
            "storage_path": str(attack_dir),
            "statistics": {
                "method": "GAUSSIAN",
                "processed_images": processed_images,
                "mean": mean,
                "std": std,
                "target_class": target_class
            },
            "message": f"Successfully created Gaussian noise dataset with {processed_images} images"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating Gaussian noise: {str(e)}"
        )


@router.post("/uniform/generate", status_code=status.HTTP_201_CREATED)
async def generate_uniform_noise_dataset(
    *,
    db: AsyncSession = Depends(get_db),
    attack_dataset_name: str = Body(..., description="Name for attack dataset"),
    base_dataset_id: UUID = Body(..., description="Base dataset ID"),
    low: float = Body(-25.0, description="Lower bound of uniform noise"),
    high: float = Body(25.0, description="Upper bound of uniform noise"),
    target_class: str = Body(..., description="Target class (noise applied inside bboxes)"),
    description: Optional[str] = Body(None, description="Optional description"),
    created_by: Optional[UUID] = Body(None, description="Optional creator ID"),
    session_id: Optional[str] = Body(None, description="SSE session ID for real-time logging")
) -> Dict[str, Any]:
    """
    Generate Uniform noise attack dataset (targeted).

    Adds random uniform noise to images inside bounding boxes of target class.

    Parameters:
        - attack_dataset_name: Name for the attack dataset
        - base_dataset_id: Base dataset to add noise to
        - low: Lower bound of uniform noise (default: -25.0)
        - high: Upper bound of uniform noise (default: 25.0)
        - target_class: Target class name (noise only applied inside bboxes of this class)

    Returns:
        - attack_dataset: Attack dataset record
        - storage_path: Path to noisy images
        - statistics: Attack statistics
    """
    try:
        attack_db, attack_dir = await noise_attack_service.generate_noise_attack_dataset(
            db=db,
            attack_name=attack_dataset_name,
            base_dataset_id=base_dataset_id,
            plugin_name="uniform_2d",
            min_val=low,
            max_val=high,
            target_class=target_class,
            targeted=True,
            description=description,
            created_by=created_by,
            session_id=session_id,
            sse_manager=sse_manager
        )

        processed_images = attack_db.parameters.get("processed_images", 0)

        return {
            "attack_dataset": schemas.AttackDataset2DResponse.model_validate(attack_db),
            "storage_path": str(attack_dir),
            "statistics": {
                "method": "UNIFORM",
                "processed_images": processed_images,
                "low": low,
                "high": high,
                "target_class": target_class
            },
            "message": f"Successfully created Uniform noise dataset with {processed_images} images"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating Uniform noise: {str(e)}"
        )


@router.post("/iterative-gradient/generate", status_code=status.HTTP_201_CREATED)
async def generate_iterative_gradient_attack_dataset(
    *,
    db: AsyncSession = Depends(get_db),
    attack_dataset_name: str = Body(..., description="Name for attack dataset"),
    model_version_id: UUID = Body(..., description="Model version ID"),
    base_dataset_id: UUID = Body(..., description="Base dataset ID"),
    max_iterations: int = Body(10000, ge=1, le=100000, description="Maximum iterations (default: 10000)"),
    step_size: float = Body(1.0, ge=0.0, description="Gradient step size (default: 1.0)"),
    epsilon: float = Body(0.03, ge=0.0, le=1.0, description="Max perturbation L-infinity constraint (default: 0.03)"),
    ncc_threshold: float = Body(0.6, ge=0.0, le=1.0, description="NCC similarity threshold (default: 0.6)"),
    stop_threshold: float = Body(0.1, ge=0.0, le=1.0, description="Stop when detections < threshold * initial"),
    target_class: str = Body(..., description="Target class (attack inside bboxes)"),
    description: Optional[str] = Body(None, description="Optional description"),
    created_by: Optional[UUID] = Body(None, description="Optional creator ID"),
    session_id: Optional[str] = Body(None, description="SSE session ID for real-time logging")
) -> Dict[str, Any]:
    """
    Generate Iterative Gradient Attack dataset with imperceptible noise.

    This attack iteratively applies gradients with epsilon constraints and NCC similarity
    checking to create imperceptible adversarial noise that fools object detection models.

    Parameters:
        - attack_dataset_name: Name for the attack dataset
        - model_version_id: Model to attack
        - base_dataset_id: Base dataset to attack
        - max_iterations: Maximum number of iterations (default: 1000)
        - step_size: Gradient step size in normalized range (default: 1.0)
        - epsilon: Maximum perturbation per pixel L-inf constraint (default: 0.03 = 3%)
        - ncc_threshold: NCC similarity threshold to preserve visual quality (default: 0.6)
        - stop_threshold: Stop when detections < threshold * initial (default: 0.1)
        - target_class: Target class name (attack only inside bboxes of this class)

    Returns:
        - attack_dataset: Attack dataset record
        - storage_path: Path to attacked images
        - statistics: Attack statistics
    """
    try:
        attack_db, attack_dir = await noise_attack_service.generate_noise_attack_dataset(
            db=db,
            attack_name=attack_dataset_name,
            base_dataset_id=base_dataset_id,
            plugin_name="iterative_gradient_2d",
            model_version_id=model_version_id,
            max_iterations=max_iterations,
            step_size=step_size,
            epsilon=epsilon,
            ncc_threshold=ncc_threshold,
            stop_threshold=stop_threshold,
            target_class=target_class,
            targeted=True,
            description=description,
            created_by=created_by,
            session_id=session_id,
            sse_manager=sse_manager
        )

        processed_images = attack_db.parameters.get("processed_images", 0)

        return {
            "id": attack_db.id,
            "name": attack_db.name,
            "attack_type": attack_db.attack_type,
            "storage_path": str(attack_dir),
            "statistics": {
                "method": "ITERATIVE_GRADIENT",
                "processed_images": processed_images,
                "max_iterations": max_iterations,
                "step_size": step_size,
                "epsilon": epsilon,
                "ncc_threshold": ncc_threshold,
                "stop_threshold": stop_threshold,
                "target_class": target_class
            },
            "message": f"Successfully created Iterative Gradient attack dataset with {processed_images} images"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating Iterative Gradient attack: {str(e)}"
        )


@router.get("/attacks/{session_id}/events")
async def noise_attack_generation_events(session_id: str):
    """
    Server-Sent Events (SSE) endpoint for real-time noise attack generation logging.

    Connect to this endpoint before calling any /generate endpoint with the same session_id.

    Usage:
        1. Connect to this endpoint: GET /noise-attack/attacks/{session_id}/events
        2. Call generation endpoint with same session_id: POST /noise-attack/{method}/generate
        3. Receive real-time progress updates via SSE
    """
    # Create session if not exists
    sse_manager.create_session(session_id)

    return StreamingResponse(
        sse_manager.event_stream(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
