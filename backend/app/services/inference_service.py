"""
Model inference orchestration services.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.exceptions import NotFoundError, ValidationError
from app.services.custom_model_service import custom_model_service

logger = logging.getLogger(__name__)


class InferenceService:
    """Coordinate model inference workflows."""

    def __init__(self):
        self.custom_model_service = custom_model_service

    async def run_inference(
        self,
        db: AsyncSession,
        model_version_id: UUID,
        image_ids: List[UUID],
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ) -> List[Dict[str, Any]]:
        """
        Run inference for a list of image IDs and return detailed detections.
        """
        model_version = await crud.od_model_version.get(db, id=model_version_id)
        if not model_version:
            raise NotFoundError(resource=f"Model version {model_version_id}")

        logger.info(
            "Running inference on %s images with model %s",
            len(image_ids),
            model_version_id,
        )

        try:
            model_info = await self.custom_model_service.get_model_info(
                str(model_version_id)
            )
            if not model_info or not model_info.get("is_loaded"):
                logger.info("Loading model %s", model_version_id)
                await self.custom_model_service.load_model(str(model_version_id))
        except Exception as exc:
            logger.warning("Could not ensure custom model is loaded: %s", exc)

        results: List[Dict[str, Any]] = []
        for image_id in image_ids:
            image = await crud.image_2d.get(db, id=image_id)
            if not image:
                logger.warning("Image %s not found, skipping", image_id)
                continue

            image_path = Path(image.storage_key)
            if not image_path.exists():
                logger.warning("Image file not found: %s", image.storage_key)
                continue

            import cv2

            img = cv2.imread(str(image_path))
            if img is None:
                logger.warning("Could not read image: %s", image.storage_key)
                continue

            try:
                inference_result = await self.custom_model_service.run_inference(
                    version_id=str(model_version_id),
                    image=img,
                    conf_threshold=conf_threshold,
                    iou_threshold=iou_threshold,
                )
            except Exception as exc:
                logger.error("Inference failed for image %s: %s", image_id, exc)
                results.append(
                    {
                        "image_id": str(image_id),
                        "detections": [],
                        "inference_time_ms": 0,
                        "status": "error",
                        "error": str(exc),
                    }
                )
                continue

            detections = [
                {
                    "class_id": det.class_id,
                    "class_name": det.class_name,
                    "confidence": det.confidence,
                    "bbox": {
                        "x1": det.bbox.x1,
                        "y1": det.bbox.y1,
                        "x2": det.bbox.x2,
                        "y2": det.bbox.y2,
                    },
                }
                for det in inference_result.detections
            ]

            results.append(
                {
                    "image_id": str(image_id),
                    "file_name": image.file_name,
                    "detections": detections,
                    "inference_time_ms": inference_result.inference_time_ms,
                    "status": "success",
                }
            )

        return results

    async def batch_inference(
        self,
        db: AsyncSession,
        model_version_id: UUID,
        dataset_id: UUID,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        batch_size: int = 32,
    ) -> Dict[str, Any]:
        """
        Run inference for all images in a dataset in batches.
        """
        images = await crud.image_2d.get_by_dataset(db, dataset_id=dataset_id)
        if not images:
            raise ValidationError(detail=f"No images in dataset {dataset_id}")

        image_ids = [img.id for img in images]
        logger.info(
            "Running batch inference on %s images from dataset %s",
            len(image_ids),
            dataset_id,
        )

        all_results: List[Dict[str, Any]] = []
        for i in range(0, len(image_ids), batch_size):
            batch_ids = image_ids[i : i + batch_size]
            batch_results = await self.run_inference(
                db=db,
                model_version_id=model_version_id,
                image_ids=batch_ids,
                conf_threshold=conf_threshold,
                iou_threshold=iou_threshold,
            )
            all_results.extend(batch_results)

        successful = sum(1 for r in all_results if r["status"] == "success")
        failed = sum(1 for r in all_results if r["status"] == "error")
        total_detections = sum(len(r["detections"]) for r in all_results)
        avg_inference_time = (
            sum(r["inference_time_ms"] for r in all_results) / len(all_results)
            if all_results
            else 0
        )

        return {
            "dataset_id": str(dataset_id),
            "model_version_id": str(model_version_id),
            "total_images": len(image_ids),
            "successful": successful,
            "failed": failed,
            "total_detections": total_detections,
            "avg_inference_time_ms": avg_inference_time,
            "results": all_results,
        }


inference_service = InferenceService()

