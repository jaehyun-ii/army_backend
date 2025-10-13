"""
Custom model management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
import logging

from app.database import get_db
from app.schemas.custom_model import (
    ModelUploadResponse,
    ModelInferenceRequest,
    ModelInferenceResponse,
    DetectionResponse,
    BoundingBoxResponse,
    ModelListResponse,
    ModelInfoResponse
)
from app.services.custom_model_service import custom_model_service
from app.ai.model_loader import model_loader

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=ModelUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_custom_model(
    *,
    db: AsyncSession = Depends(get_db),
    model_name: str = Form(...),
    version: str = Form(...),
    framework: str = Form(...),
    description: Optional[str] = Form(None),
    weights_file: UploadFile = File(...),
    config_file: UploadFile = File(...),
    adapter_file: UploadFile = File(...),
    requirements_file: Optional[UploadFile] = File(None),
) -> ModelUploadResponse:
    """
    Upload a custom object detection model.

    Required files:
    - weights_file: Model weights (.pt, .pth, .onnx, etc.)
    - config_file: config.yaml with model configuration
    - adapter_file: adapter.py implementing BaseObjectDetector

    Optional files:
    - requirements_file: requirements.txt for dependencies

    Form data:
    - model_name: Name of the model
    - version: Version string
    - framework: Framework (pytorch, tensorflow, onnx, etc.)
    - description: Optional description
    """
    try:
        # Validate file types
        if not config_file.filename.endswith('.yaml'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="config_file must be a .yaml file"
            )

        if not adapter_file.filename.endswith('.py'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="adapter_file must be a .py file"
            )

        if requirements_file and not requirements_file.filename.endswith('.txt'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="requirements_file must be a .txt file"
            )

        # Upload model
        result = await custom_model_service.upload_model(
            db=db,
            model_name=model_name,
            version=version,
            framework=framework,
            weights_file=weights_file.file,
            weights_filename=weights_file.filename,
            config_file=config_file.file,
            adapter_file=adapter_file.file,
            requirements_file=requirements_file.file if requirements_file else None,
            description=description
        )

        return ModelUploadResponse(
            model_id=result["model_id"],
            version_id=result["version_id"],
            upload_status=result["status"],
            message=result["message"]
        )

    except ValueError as e:
        logger.warning(f"Validation error uploading model: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model configuration: {str(e)}"
        )
    except FileNotFoundError as e:
        logger.warning(f"File not found error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Required model file not found"
        )
    except PermissionError as e:
        logger.error(f"Permission error uploading model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage permission error"
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading model: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during model upload"
        )


@router.post("/{version_id}/load", response_model=ModelInfoResponse)
async def load_model(
    version_id: UUID,
) -> ModelInfoResponse:
    """
    Load a custom model into memory for inference.

    Args:
        version_id: Model version ID
    """
    try:
        model_info = await custom_model_service.load_model(str(version_id))

        return ModelInfoResponse(
            model_id=str(version_id),
            model_name=model_info.get("config", {}).get("model_name", "unknown"),
            version=model_info.get("config", {}).get("version", "1.0"),
            framework=model_info.get("config", {}).get("framework", "custom"),
            is_loaded=model_info["is_loaded"],
            class_names=model_info["class_names"],
            num_classes=model_info["num_classes"],
            config=model_info["config"],
            created_at=model_info.get("created_at")
        )

    except FileNotFoundError as e:
        logger.warning(f"Model files not found for {version_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model files not found. Please check if the model was uploaded correctly."
        )
    except ValueError as e:
        logger.warning(f"Validation error loading model {version_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model validation failed: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading model {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while loading model"
        )


@router.post("/{version_id}/test-inference", response_model=ModelInferenceResponse)
async def test_inference(
    version_id: UUID,
    request: ModelInferenceRequest,
) -> ModelInferenceResponse:
    """
    Test inference: Load model, run inference, unload model, return results.

    This endpoint automatically manages model loading/unloading for quick testing.

    Args:
        version_id: Model version ID
        request: Inference request with image data
    """
    model_id_str = str(version_id)
    was_loaded = model_id_str in model_loader.get_loaded_models()

    try:
        # 1. Load model if not already loaded
        if not was_loaded:
            logger.info(f"Loading model {model_id_str} for test inference")
            await custom_model_service.load_model(model_id_str)

        # 2. Decode image
        if request.image_base64:
            image = await custom_model_service.decode_image(request.image_base64)
        elif request.image_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="image_url not yet supported, use image_base64"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either image_base64 or image_url must be provided"
            )

        # 3. Run inference
        result = await custom_model_service.run_inference(
            version_id=model_id_str,
            image=image,
            conf_threshold=request.conf_threshold,
            iou_threshold=request.iou_threshold
        )

        # Convert to response format
        detections = [
            DetectionResponse(
                bbox=BoundingBoxResponse(
                    x1=det.bbox.x1,
                    y1=det.bbox.y1,
                    x2=det.bbox.x2,
                    y2=det.bbox.y2
                ),
                class_id=det.class_id,
                class_name=det.class_name,
                confidence=det.confidence
            )
            for det in result.detections
        ]

        # Get model info
        model_info = await custom_model_service.get_model_info(model_id_str)

        response = ModelInferenceResponse(
            detections=detections,
            inference_time_ms=result.inference_time_ms,
            model_info=model_info or {}
        )

        # 4. Unload model if it wasn't loaded before
        if not was_loaded:
            logger.info(f"Unloading model {model_id_str} after test inference")
            await custom_model_service.unload_model(model_id_str)

        return response

    except HTTPException:
        # Cleanup on error if we loaded the model
        if not was_loaded and model_id_str in model_loader.get_loaded_models():
            try:
                await custom_model_service.unload_model(model_id_str)
            except Exception as e:
                logger.error(f"Failed to unload model after error: {e}")
        raise
    except Exception as e:
        # Cleanup on error if we loaded the model
        if not was_loaded and model_id_str in model_loader.get_loaded_models():
            try:
                await custom_model_service.unload_model(model_id_str)
            except Exception as e2:
                logger.error(f"Failed to unload model after error: {e2}")

        logger.error(f"Unexpected error in test inference on {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during test inference"
        )


@router.post("/{version_id}/predict", response_model=ModelInferenceResponse)
async def run_inference(
    version_id: UUID,
    request: ModelInferenceRequest,
) -> ModelInferenceResponse:
    """
    Run inference on an image using a custom model.

    Model must be loaded first using /load endpoint.

    Args:
        version_id: Model version ID
        request: Inference request with image data
    """
    try:
        # Decode image
        if request.image_base64:
            image = await custom_model_service.decode_image(request.image_base64)
        elif request.image_url:
            # TODO: Implement image download from URL
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="image_url not yet supported, use image_base64"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either image_base64 or image_url must be provided"
            )

        # Run inference
        result = await custom_model_service.run_inference(
            version_id=str(version_id),
            image=image,
            conf_threshold=request.conf_threshold,
            iou_threshold=request.iou_threshold
        )

        # Convert to response format
        detections = [
            DetectionResponse(
                bbox=BoundingBoxResponse(
                    x1=det.bbox.x1,
                    y1=det.bbox.y1,
                    x2=det.bbox.x2,
                    y2=det.bbox.y2
                ),
                class_id=det.class_id,
                class_name=det.class_name,
                confidence=det.confidence
            )
            for det in result.detections
        ]

        # Get model info
        model_info = await custom_model_service.get_model_info(str(version_id))

        return ModelInferenceResponse(
            detections=detections,
            inference_time_ms=result.inference_time_ms,
            model_info=model_info or {}
        )

    except ValueError as e:
        logger.warning(f"Invalid input for inference: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid inference input: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error running inference on {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during inference"
        )


@router.get("/", response_model=List[ModelListResponse])
async def list_all_models(
    db: AsyncSession = Depends(get_db),
) -> List[ModelListResponse]:
    """
    List all uploaded models (both loaded and unloaded).
    """
    from app.models.model_repo import ODModelVersion, ODModel
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    # Get all model versions from DB with joined model info
    result = await db.execute(
        select(ODModelVersion)
        .options(joinedload(ODModelVersion.model))
        .order_by(ODModelVersion.created_at.desc())
    )
    db_models = result.unique().scalars().all()

    # Get loaded models info
    loaded_models = model_loader.get_loaded_models()

    response_list = []
    for db_model in db_models:
        model_id_str = str(db_model.id)
        is_loaded = model_id_str in loaded_models

        # Get class count from loaded model or from DB
        num_classes = 0
        if is_loaded:
            num_classes = loaded_models[model_id_str]["num_classes"]
        elif db_model.labelmap and isinstance(db_model.labelmap, dict):
            num_classes = len(db_model.labelmap.get("classes", []))
        elif db_model.classes:
            num_classes = len(db_model.classes)

        # Get model name
        model_name = "Unknown"
        if db_model.model:
            model_name = db_model.model.name
        elif is_loaded:
            model_name = loaded_models[model_id_str]["config"].get("model_name", "Unknown")

        response_list.append(
            ModelListResponse(
                model_id=model_id_str,
                model_name=model_name,
                version=db_model.version,
                framework=db_model.framework.value if db_model.framework else "custom",
                is_loaded=is_loaded,
                num_classes=num_classes,
                created_at=db_model.created_at.isoformat() if db_model.created_at else None
            )
        )

    return response_list


@router.get("/loaded", response_model=List[ModelListResponse])
async def list_loaded_models() -> List[ModelListResponse]:
    """
    List all models currently loaded in memory.
    """
    loaded_models = model_loader.get_loaded_models()

    return [
        ModelListResponse(
            model_id=model_id,
            model_name=info["config"].get("model_name", "unknown"),
            version=info["config"].get("version", "1.0"),
            framework=info["config"].get("framework", "custom"),
            is_loaded=info["is_loaded"],
            num_classes=info["num_classes"],
            created_at=info.get("created_at")
        )
        for model_id, info in loaded_models.items()
    ]


@router.delete("/{version_id}/unload", status_code=status.HTTP_204_NO_CONTENT)
async def unload_model(version_id: UUID):
    """
    Unload a model from memory.

    Args:
        version_id: Model version ID
    """
    try:
        await custom_model_service.unload_model(str(version_id))
    except KeyError:
        logger.warning(f"Model {version_id} not loaded, cannot unload")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {version_id} is not currently loaded"
        )
    except Exception as e:
        logger.error(f"Unexpected error unloading model {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while unloading model"
        )


@router.get("/{version_id}/info", response_model=ModelInfoResponse)
async def get_model_info(version_id: UUID) -> ModelInfoResponse:
    """
    Get information about a model (must be loaded first).

    Args:
        version_id: Model version ID
    """
    model_info = await custom_model_service.get_model_info(str(version_id))

    if not model_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {version_id} not loaded. Load it first using /load endpoint."
        )

    return ModelInfoResponse(
        model_id=str(version_id),
        model_name=model_info.get("config", {}).get("model_name", "unknown"),
        version=model_info.get("config", {}).get("version", "1.0"),
        framework=model_info.get("config", {}).get("framework", "custom"),
        is_loaded=model_info["is_loaded"],
        class_names=model_info["class_names"],
        num_classes=model_info["num_classes"],
        config=model_info["config"],
        created_at=model_info.get("created_at")
    )
