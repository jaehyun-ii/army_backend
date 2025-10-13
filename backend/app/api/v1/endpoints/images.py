"""
Image endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import List, Dict, Any
from uuid import UUID

from app.database import get_db
from app.models.dataset_2d import Image2D
from app.models.inference import ImageDetection

router = APIRouter()


@router.get("/{image_id}/detections")
async def get_image_detections(
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Get detection results for a specific image.

    Returns:
        List of detections with class, confidence, and bounding box info
    """
    # Query detections for this image
    result = await db.execute(
        select(ImageDetection)
        .filter(ImageDetection.image_id == image_id)
        .order_by(ImageDetection.confidence.desc())
    )
    detections = result.scalars().all()

    # Format response
    detection_list = []
    for det in detections:
        detection_list.append({
            "id": str(det.id),
            "class_name": det.class_name,
            "class_id": det.class_id,
            "confidence": round(det.confidence, 3),
            "bbox": {
                "x1": det.bbox_x1,
                "y1": det.bbox_y1,
                "x2": det.bbox_x2,
                "y2": det.bbox_y2,
            }
        })

    return detection_list
