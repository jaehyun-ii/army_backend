"""
Dataset management, statistics, and cleanup services.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, joinedload

from app import crud, schemas
from app.core.exceptions import NotFoundError
from app.models.dataset_2d import Dataset2D, Image2D
from app.models.inference import DatasetClassStatistics, InferenceMetadata
from app.utils.storage import storage_manager
from app.services.custom_model_service import custom_model_service
import cv2

logger = logging.getLogger(__name__)


class DatasetStatisticsService:
    """Provide statistics, imports, and cleanup for datasets."""

    def __init__(
        self,
        *,
        storage=storage_manager,
        dataset_repository=crud.dataset_2d,
        image_repository=crud.image_2d,
        inference_service=custom_model_service,
    ):
        self.storage = storage
        self.dataset_repository = dataset_repository
        self.image_repository = image_repository
        self.inference_service = inference_service

    async def import_images_batch(
        self,
        db: AsyncSession,
        dataset_id: UUID,
        image_paths: List[str],
    ) -> schemas.Dataset2DResponse:
        dataset = await self.dataset_repository.get(db, id=dataset_id)
        if not dataset:
            raise NotFoundError(resource=f"Dataset {dataset_id}")

        logger.info("Importing %s images to dataset %s", len(image_paths), dataset.name)

        for path in image_paths:
            image_path = Path(path)
            if not image_path.exists():
                logger.warning("Image not found: %s, skipping", path)
                continue

            try:
                image_data = schemas.ImageCreate(
                    dataset_id=dataset_id,
                    file_name=image_path.name,
                    storage_key=str(image_path),
                )
                await self.image_repository.create(db, obj_in=image_data)
            except Exception as exc:
                logger.error("Failed to import image %s: %s", path, exc)

        await db.refresh(dataset)
        return dataset

    async def list_datasets(
        self,
        db: AsyncSession,
        skip: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(
                Dataset2D,
                func.count(Image2D.id).label("image_count"),
            )
            .outerjoin(
                Image2D,
                (Dataset2D.id == Image2D.dataset_id)
                & (Image2D.deleted_at.is_(None)),
            )
            .filter(Dataset2D.deleted_at.is_(None))
            .group_by(Dataset2D.id)
            .offset(skip)
            .limit(limit)
        )

        summaries: List[Dict[str, Any]] = []
        for dataset, image_count in result.all():
            summaries.append(
                {
                    "id": dataset.id,
                    "name": dataset.name,
                    "description": dataset.description,
                    "image_count": image_count,
                    "created_at": dataset.created_at,
                    "updated_at": dataset.updated_at,
                }
            )
        return summaries

    async def list_dataset_images(
        self,
        db: AsyncSession,
        dataset_id: UUID,
        skip: int,
        limit: int,
    ) -> List[Image2D]:
        dataset = await self.dataset_repository.get(db, id=dataset_id)
        if not dataset:
            raise NotFoundError(resource=f"Dataset {dataset_id}")

        images = await self.image_repository.get_by_dataset(
            db,
            dataset_id=dataset_id,
            skip=skip,
            limit=limit,
        )
        return images

    async def get_dataset_statistics(
        self,
        db: AsyncSession,
        dataset_id: UUID,
    ) -> Dict[str, Any]:
        result = await db.execute(
            select(Dataset2D).filter(
                Dataset2D.id == dataset_id,
                Dataset2D.deleted_at.is_(None),
            )
        )
        dataset = result.scalar_one_or_none()
        if not dataset:
            raise NotFoundError(resource=f"Dataset {dataset_id}")

        image_result = await db.execute(
            select(Image2D).filter(
                Image2D.dataset_id == dataset_id,
                Image2D.deleted_at.is_(None),
            )
        )
        image_count = len(image_result.scalars().all())

        try:
            storage_info = self.storage.get_dataset_info(dataset.storage_path)
            total_size_bytes = storage_info["total_size_bytes"]
        except (FileNotFoundError, OSError) as exc:
            logger.warning(
                "Storage path not accessible: %s. Error: %s",
                dataset.storage_path,
                exc,
            )
            total_size_bytes = 0

        return {
            "dataset_id": str(dataset.id),
            "name": dataset.name,
            "image_count": image_count,
            "storage_path": dataset.storage_path,
            "total_size_bytes": total_size_bytes,
            "created_at": dataset.created_at.isoformat(),
            "metadata": dataset.metadata_,
        }

    async def get_dataset_detection_statistics(
        self,
        db: AsyncSession,
        dataset_id: UUID,
        model_version_id: UUID,
        conf_threshold: float = 0.25,
    ) -> Dict[str, Any]:
        from collections import Counter

        dataset_result = await db.execute(
            select(Dataset2D).filter(
                Dataset2D.id == dataset_id,
                Dataset2D.deleted_at.is_(None),
            )
        )
        dataset = dataset_result.scalars().first()
        if not dataset:
            raise NotFoundError(resource=f"Dataset {dataset_id}")

        images_result = await db.execute(
            select(Image2D).filter(
                Image2D.dataset_id == dataset_id,
                Image2D.deleted_at.is_(None),
            )
        )
        images = images_result.scalars().all()

        total_detections = 0
        class_counter: Counter[str] = Counter()
        images_with_detections = 0

        for img in images:
            img_path = img.storage_key
            if not Path(img_path).exists():
                continue

            image_array = cv2.imread(str(img_path))
            if image_array is None:
                continue

            result = await self.inference_service.run_inference(
                version_id=str(model_version_id),
                image=image_array,
                conf_threshold=conf_threshold,
            )

            if result.detections:
                images_with_detections += 1
                total_detections += len(result.detections)
                for det in result.detections:
                    class_counter[det.class_name] += 1

        basic_stats = await self.get_dataset_statistics(db, dataset_id)

        return {
            **basic_stats,
            "detection_statistics": {
                "model_version_id": str(model_version_id),
                "conf_threshold": conf_threshold,
                "total_detections": total_detections,
                "images_with_detections": images_with_detections,
                "images_without_detections": len(images) - images_with_detections,
                "class_counts": dict(class_counter),
                "unique_classes": len(class_counter),
                "average_detections_per_image": (
                    total_detections / len(images) if images else 0
                ),
            },
        }

    async def get_top_classes(
        self,
        db: AsyncSession,
        dataset_id: UUID,
        limit: int,
    ) -> Dict[str, Any]:
        dataset_result = await db.execute(
            select(Dataset2D)
            .options(joinedload(Dataset2D.inference_metadata))
            .filter(Dataset2D.id == dataset_id, Dataset2D.deleted_at.is_(None))
        )
        dataset = dataset_result.scalar_one_or_none()
        if not dataset:
            raise NotFoundError(resource=f"Dataset {dataset_id}")

        stats_result = await db.execute(
            select(DatasetClassStatistics)
            .filter(DatasetClassStatistics.dataset_id == dataset_id)
            .order_by(DatasetClassStatistics.detection_count.desc())
            .limit(limit)
        )
        stats = stats_result.scalars().all()

        if not stats:
            image_result = await db.execute(
                select(Image2D).filter(
                    Image2D.dataset_id == dataset_id,
                    Image2D.deleted_at.is_(None),
                )
            )
            images = image_result.scalars().all()
            return {
                "dataset_id": str(dataset_id),
                "dataset_name": dataset.name,
                "total_images": len(images),
                "top_classes": [],
                "source": "none",
                "cached": False,
                "message": "No inference metadata available for this dataset",
            }

        inference_meta: Optional[InferenceMetadata] = dataset.inference_metadata
        total_images = inference_meta.total_images if inference_meta else 0
        total_detections = inference_meta.total_detections if inference_meta else 0

        top_classes = [
            {
                "class_name": s.class_name,
                "count": s.detection_count,
                "percentage": round((s.detection_count / total_detections) * 100, 2)
                if total_detections > 0
                else 0,
                "avg_confidence": round(s.avg_confidence, 3),
                "image_count": s.image_count,
            }
            for s in stats
        ]

        return {
            "dataset_id": str(dataset_id),
            "dataset_name": dataset.name,
            "total_images": total_images,
            "top_classes": top_classes,
            "source": "metadata",
            "cached": True,
        }

    async def get_class_distribution(
        self,
        db: AsyncSession,
        dataset_id: UUID,
    ) -> Dict[str, Any]:
        dataset = await self.dataset_repository.get(db, id=dataset_id)
        if not dataset:
            raise NotFoundError(resource=f"Dataset {dataset_id}")

        from app.models.inference import DatasetClassStatistics

        result = await db.execute(
            select(DatasetClassStatistics).where(
                DatasetClassStatistics.dataset_id == dataset_id
            )
        )
        class_stats = result.scalars().all()

        if class_stats:
            return {
                "dataset_id": str(dataset_id),
                "dataset_name": dataset.name,
                "classes": [
                    {
                        "class_name": stat.class_name,
                        "count": stat.count,
                        "percentage": stat.percentage,
                        "avg_confidence": stat.avg_confidence,
                    }
                    for stat in class_stats
                ],
                "total_classes": len(class_stats),
                "source": "statistics_table",
            }

        metadata = dataset.metadata_ or {}
        return {
            "dataset_id": str(dataset_id),
            "dataset_name": dataset.name,
            "classes": metadata.get("classes", []),
            "total_classes": len(metadata.get("classes", [])),
            "source": "metadata",
        }

    def delete_dataset_with_files(
        self,
        db: Session,
        dataset_id: UUID,
    ) -> bool:
        dataset = db.query(Dataset2D).filter(
            Dataset2D.id == dataset_id,
            Dataset2D.deleted_at.is_(None),
        ).first()

        if not dataset:
            raise NotFoundError(resource=f"Dataset {dataset_id}")

        self.storage.delete_dataset_folder(dataset.storage_path)

        db.query(Image2D).filter(Image2D.dataset_id == dataset_id).update(
            {"deleted_at": db.func.now()}
        )

        from datetime import datetime, timezone

        dataset.deleted_at = datetime.now(timezone.utc)
        db.commit()
        return True


dataset_statistics_service = DatasetStatisticsService()
