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
from app.services.estimator_loader_service import estimator_loader
from app.services.model_inference_service import model_inference_service

logger = logging.getLogger(__name__)


class InferenceService:
    """Coordinate model inference workflows."""

    async def run_inference(
        self,
        db: AsyncSession,
        model_id: UUID,
        image_ids: List[UUID],
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ) -> List[Dict[str, Any]]:
        """
        Run inference for a list of image IDs and return detailed detections.
        This function now manages the lifecycle of a temporary estimator.
        """
        estimator_id = f"inference__{model_id}"
        logger.info(
            "Running inference on %s images with model %s (using estimator '%s')",
            len(image_ids),
            model_id,
            estimator_id,
        )

        try:
            # 1. Load the model as a temporary estimator
            await estimator_loader.load_estimator_from_db(
                db=db,
                model_id=model_id,
                estimator_id=estimator_id
            )

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
                    # 2. Run inference using the new service
                    inference_result = await model_inference_service.run_inference(
                        version_id=estimator_id,
                        image=img,
                        conf_threshold=conf_threshold,
                        iou_threshold=iou_threshold,
                    )
                except Exception as exc:
                    logger.error("Inference failed for image %s: %s", image_id, exc)
                    results.append({
                        "image_id": str(image_id),
                        "detections": [],
                        "status": "error",
                        "error": str(exc),
                    })
                    continue

                # Convert results
                detections = []
                for det in inference_result.detections:
                    x1 = det.bbox.x_center - det.bbox.width / 2
                    y1 = det.bbox.y_center - det.bbox.height / 2
                    x2 = det.bbox.x_center + det.bbox.width / 2
                    y2 = det.bbox.y_center + det.bbox.height / 2
                    detections.append({
                        "class_id": det.class_id,
                        "class_name": det.class_name,
                        "confidence": det.confidence,
                        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    })

                results.append({
                    "image_id": str(image_id),
                    "file_name": image.file_name,
                    "detections": detections,
                    "inference_time_ms": inference_result.inference_time_ms,
                    "status": "success",
                })

            return results

        finally:
            # 3. Unload the temporary estimator
            if model_inference_service.is_loaded(estimator_id):
                model_inference_service.unregister_estimator(estimator_id)
                logger.info(f"Unloaded temporary estimator '{estimator_id}'")

    async def batch_inference(
        self,
        db: AsyncSession,
        model_id: UUID,
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
            # This now uses the refactored run_inference, which handles its own estimator lifecycle
            batch_results = await self.run_inference(
                db=db,
                model_id=model_id,
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
            "model_id": str(model_id),
            "total_images": len(image_ids),
            "successful": successful,
            "failed": failed,
            "total_detections": total_detections,
            "avg_inference_time_ms": avg_inference_time,
            "results": all_results,
        }


inference_service = InferenceService()

