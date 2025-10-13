"""
Dataset service endpoints for upload and management operations.
These endpoints handle business logic and file operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from uuid import UUID
import os
import shutil
from pathlib import Path

from app.database import get_db
from app import schemas
from app.services.dataset_upload_service import dataset_upload_service
from app.services.dataset_management_service import dataset_statistics_service
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
    InternalServerError
)

router = APIRouter()


@router.post("/upload-folder", status_code=status.HTTP_201_CREATED)
async def upload_dataset_folder(
    *,
    db: AsyncSession = Depends(get_db),
    source_folder: str = Body(..., description="Path to the folder to upload"),
    dataset_name: str = Body(..., description="Name for the dataset"),
    description: Optional[str] = Body(None, description="Optional dataset description"),
    owner_id: Optional[UUID] = Body(None, description="Optional owner UUID"),
    inference_metadata_path: Optional[str] = Body(None, description="Optional path to YOLO inference metadata JSON"),
) -> Dict[str, Any]:
    """Upload a dataset from a local folder.

    This endpoint accepts a folder path and uploads all images found in that folder,
    creating dataset and image records in the database.

    The folder should contain:
    - Image files (.jpg, .jpeg, .png, .bmp, .tiff, .webp)
    - Optional metadata.json file with dataset metadata

    If inference_metadata_path is provided, the YOLO inference results will be parsed
    and stored in the database for fast class distribution queries.

    Returns:
        Dictionary with dataset info, image count, list of uploaded images, and optional metadata stats
    """
    try:
        dataset, images, metadata_stats = await dataset_upload_service.upload_dataset_from_folder(
            db=db,
            source_folder=source_folder,
            dataset_name=dataset_name,
            description=description,
            owner_id=owner_id,
            inference_metadata_path=inference_metadata_path
        )

        response = {
            "dataset": schemas.Dataset2DResponse.model_validate(dataset),
            "image_count": len(images),
            "images": [schemas.ImageResponse.model_validate(img) for img in images],
            "message": f"Successfully uploaded dataset with {len(images)} images"
        }

        if metadata_stats:
            response["metadata_processed"] = True
            response["metadata_stats"] = metadata_stats
        else:
            response["metadata_processed"] = False

        return response
    except (NotFoundError, ValidationError, ConflictError) as e:
        # Custom exceptions are already HTTPExceptions, re-raise as-is
        raise
    except Exception as e:
        # Catch unexpected errors and convert to InternalServerError
        raise InternalServerError(detail=f"Error uploading dataset: {str(e)}")


@router.get("/{dataset_id}/stats")
async def get_dataset_statistics(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get statistics for a dataset including storage info.

    Returns:
        - dataset_id: Dataset UUID
        - name: Dataset name
        - image_count: Number of images
        - storage_path: Physical storage location
        - total_size_bytes: Total storage size
        - created_at: Creation timestamp
        - metadata: Dataset metadata
    """
    try:
        stats = await dataset_statistics_service.get_dataset_statistics(db, dataset_id)
        return stats
    except (NotFoundError, ValidationError, ConflictError) as e:
        # Custom exceptions are already HTTPExceptions, re-raise as-is
        raise
    except Exception as e:
        # Catch unexpected errors
        raise InternalServerError(detail=f"Error getting dataset statistics: {str(e)}")


@router.post("/{dataset_id}/detection-stats")
async def get_dataset_detection_statistics(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    detect_model_version_id: UUID = Body(..., description="Model version ID for detection"),
    conf_threshold: float = Body(0.25, ge=0.0, le=1.0, description="Confidence threshold"),
) -> Dict[str, Any]:
    """Get detection statistics for a dataset.

    Runs object detection on all images in the dataset and returns:
        - Basic dataset statistics (image count, storage size, etc.)
        - Detection statistics:
            - total_detections: Total number of detections across all images
            - images_with_detections: Number of images with at least one detection
            - images_without_detections: Number of images with no detections
            - class_counts: Dictionary of {class_name: count} for all detected classes
            - unique_classes: Number of unique classes detected
            - average_detections_per_image: Average detections per image

    Args:
        dataset_id: Dataset UUID
        model_version_id: Model version to use for detection
        conf_threshold: Confidence threshold for detections (0.0 - 1.0)

    Returns:
        Complete dataset statistics with detection information
    """
    try:
        stats = await dataset_statistics_service.get_dataset_detection_statistics(
            db=db,
            dataset_id=dataset_id,
            model_version_id=detect_model_version_id,
            conf_threshold=conf_threshold
        )
        return stats
    except (NotFoundError, ValidationError, ConflictError) as e:
        # Custom exceptions are already HTTPExceptions, re-raise as-is
        raise
    except Exception as e:
        # Catch unexpected errors and convert to InternalServerError
        raise InternalServerError(detail=f"Error getting detection statistics: {str(e)}")


@router.post("/upload-multipart", status_code=status.HTTP_201_CREATED)
async def upload_dataset_multipart(
    *,
    db: AsyncSession = Depends(get_db),
    dataset_name: str = Form(..., description="Name for the dataset"),
    description: Optional[str] = Form(None, description="Optional dataset description"),
    images: List[UploadFile] = File(..., description="Image files to upload"),
    metadata: Optional[UploadFile] = File(None, description="Optional YOLO inference metadata JSON"),
) -> Dict[str, Any]:
    """Upload a dataset via multipart form data (browser file upload).

    This endpoint accepts files uploaded from a browser form and creates
    a dataset with the uploaded images.

    Returns:
        Dictionary with dataset info, image count, and list of uploaded images
    """
    try:
        # 임시 폴더 생성
        import uuid
        temp_dir = Path("storage/temp") / f"upload_{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # 이미지 파일 저장
        for image in images:
            # 파일명에서 경로 제거 (basename만 사용)
            filename = os.path.basename(image.filename)
            file_path = temp_dir / filename

            # 파일 저장
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)

        # 메타데이터 파일 저장 (선택사항)
        metadata_path = None
        if metadata:
            # 파일명에서 경로 제거
            metadata_filename = os.path.basename(metadata.filename)
            metadata_path = temp_dir / metadata_filename
            with open(metadata_path, "wb") as buffer:
                shutil.copyfileobj(metadata.file, buffer)

        # dataset_service를 사용해서 데이터셋 생성
        dataset, image_records, metadata_stats = await dataset_upload_service.upload_dataset_from_folder(
            db=db,
            source_folder=str(temp_dir),
            dataset_name=dataset_name,
            description=description,
            owner_id=None,
            inference_metadata_path=str(metadata_path) if metadata_path else None
        )

        response = {
            "dataset": schemas.Dataset2DResponse.model_validate(dataset),
            "image_count": len(image_records),
            "images": [schemas.ImageResponse.model_validate(img) for img in image_records],
            "message": f"Successfully uploaded dataset with {len(image_records)} images"
        }

        if metadata_stats:
            response["metadata_processed"] = True
            response["metadata_stats"] = metadata_stats
        else:
            response["metadata_processed"] = False

        # 임시 폴더 삭제
        shutil.rmtree(temp_dir, ignore_errors=True)

        return response

    except (NotFoundError, ValidationError, ConflictError) as e:
        # Custom exceptions are already HTTPExceptions, re-raise as-is
        raise
    except Exception as e:
        # Catch unexpected errors and convert to InternalServerError
        # 임시 폴더 정리
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise InternalServerError(detail=f"Error uploading dataset: {str(e)}")


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset_with_files(
    dataset_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete a 2D dataset and its files from storage.

    This endpoint performs:
    1. Physical file deletion from storage
    2. Soft delete of all images in DB
    3. Soft delete of dataset in DB
    """
    try:
        dataset_statistics_service.delete_dataset_with_files(db, dataset_id)
    except (NotFoundError, ValidationError, ConflictError) as e:
        # Custom exceptions are already HTTPExceptions, re-raise as-is
        raise
    except Exception as e:
        # Catch unexpected errors
        raise InternalServerError(detail=f"Error deleting dataset: {str(e)}")
