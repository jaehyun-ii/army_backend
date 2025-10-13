"""
Dataset upload service and helpers.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    ConflictError,
    InternalServerError,
    NotFoundError,
    ValidationError,
)
from app.models.dataset_2d import Dataset2D, Image2D
from app.schemas.dataset_2d import Dataset2DCreate, ImageCreate
from app.utils.storage import storage_manager

logger = logging.getLogger(__name__)

DEFAULT_CLASS_NAME = "unknown"
DEFAULT_CLASS_ID = 0
DEFAULT_CONFIDENCE = 0.0
DEFAULT_BBOX_COORD = 0.0
DEFAULT_MODEL_NAME = "unknown"
BATCH_SIZE = 1000


@dataclass
class DatasetUploadContext:
    source_folder: str
    dataset_name: str
    description: Optional[str]
    owner_id: Optional[UUID]
    inference_metadata_path: Optional[str]


@dataclass
class DatasetIngestionResult:
    storage_path: str
    metadata: Dict[str, Any]
    image_list: List[Dict[str, Any]]


class DatasetUploadValidator:
    """Validate dataset upload inputs."""

    @staticmethod
    def validate_metadata_path(metadata_path: Optional[str]) -> Optional[Path]:
        if not metadata_path:
            return None

        metadata_path_obj = Path(metadata_path).resolve()
        if not metadata_path_obj.exists():
            raise NotFoundError(
                resource=f"Inference metadata file at {metadata_path}"
            )

        try:
            if str(metadata_path_obj).startswith(("/etc", "/sys", "/proc", "/dev")):
                raise ValidationError(
                    detail="Access to system directories is not allowed"
                )
            if not metadata_path_obj.is_file():
                raise ValidationError(detail="Metadata path must be a regular file")
        except (OSError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(detail=f"Invalid metadata path: {str(exc)}") from exc

        return metadata_path_obj


class DatasetFolderIngestor:
    """Handle copying uploaded dataset folders into managed storage."""

    def __init__(self, storage):
        self._storage = storage

    def ingest(self, context: DatasetUploadContext) -> DatasetIngestionResult:
        storage_path, metadata, image_list = self._storage.save_dataset_folder(
            source_folder=context.source_folder,
            dataset_name=context.dataset_name,
            owner_id=context.owner_id,
        )
        logger.info("Saved %s images to storage at %s", len(image_list), storage_path)

        return DatasetIngestionResult(
            storage_path=storage_path,
            metadata=metadata,
            image_list=image_list,
        )

    def cleanup(self, storage_path: str) -> None:
        try:
            self._storage.delete_dataset_folder(storage_path)
            logger.info("Successfully cleaned up storage at %s", storage_path)
        except Exception as cleanup_error:
            logger.error(
                "Failed to cleanup storage: %s",
                cleanup_error,
                exc_info=True,
            )


class DatasetPersistenceManager:
    """Persist dataset and image records."""

    async def create_dataset_records(
        self,
        db: AsyncSession,
        context: DatasetUploadContext,
        ingestion: DatasetIngestionResult,
    ) -> Tuple[Dataset2D, List[Image2D]]:
        dataset_data = Dataset2DCreate(
            name=context.dataset_name,
            description=context.description or ingestion.metadata.get("description", ""),
            storage_path=ingestion.storage_path,
            metadata=ingestion.metadata,
        )

        dataset = Dataset2D(
            name=dataset_data.name,
            description=dataset_data.description,
            owner_id=context.owner_id,
            storage_path=dataset_data.storage_path,
            metadata_=dataset_data.metadata,
        )
        db.add(dataset)
        await db.flush()

        images: List[Image2D] = []
        for image_info in ingestion.image_list:
            image = Image2D(
                dataset_id=dataset.id,
                file_name=image_info["file_name"],
                storage_key=image_info["storage_key"],
                width=image_info["width"],
                height=image_info["height"],
                mime_type=image_info["mime_type"],
                uploaded_by=context.owner_id,
                metadata_={
                    "size_bytes": image_info["size_bytes"],
                    "relative_path": image_info["relative_path"],
                },
            )
            db.add(image)
            images.append(image)

        await db.flush()
        return dataset, images


class InferenceMetadataProcessor:
    """Process inference metadata files associated with datasets."""

    async def process(
        self,
        db: AsyncSession,
        dataset_id: UUID,
        metadata_path: str,
        uploaded_images: List[Image2D],
    ) -> Dict[str, Any]:
        from datetime import datetime, timezone
        from collections import defaultdict
        from app.models.inference import (
            InferenceMetadata,
            ImageDetection,
            DatasetClassStatistics,
        )

        result = await db.execute(
            select(InferenceMetadata).filter(
                InferenceMetadata.dataset_id == dataset_id
            )
        )
        existing_metadata = result.scalar_one_or_none()
        if existing_metadata:
            raise ConflictError(
                detail=(
                    f"Inference metadata already exists for dataset {dataset_id}. "
                    "Please delete the existing metadata before uploading new data."
                )
            )

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
        except FileNotFoundError as exc:
            raise NotFoundError(resource=f"Metadata file at {metadata_path}") from exc
        except PermissionError as exc:
            raise ValidationError(
                detail="Permission denied: Cannot read metadata file"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(
                detail=f"Invalid JSON format at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc
        except UnicodeDecodeError as exc:
            raise ValidationError(detail="Invalid file encoding. Expected UTF-8.") from exc
        except OSError as exc:
            raise InternalServerError(detail=f"Error reading metadata file: {str(exc)}") from exc

        from app.schemas.inference import InferenceMetadataJSON

        try:
            validated_metadata = InferenceMetadataJSON(**raw_json)
            metadata_json = validated_metadata.model_dump(by_alias=True)
        except ValueError as exc:
            raise ValidationError(detail=f"Invalid metadata schema: {str(exc)}") from exc

        timestamp_str = metadata_json.get("timestamp", "")
        try:
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str.replace("Z", "+00:00")
            inference_timestamp = datetime.now(timezone.utc)
            inference_timestamp = datetime.fromisoformat(timestamp_str)
        except (ValueError, AttributeError):
            inference_timestamp = datetime.now(timezone.utc)

        if inference_timestamp.tzinfo is not None:
            inference_timestamp = inference_timestamp.replace(tzinfo=None)

        inference_meta = InferenceMetadata(
            dataset_id=dataset_id,
            model_name=metadata_json.get("model", DEFAULT_MODEL_NAME),
            inference_timestamp=inference_timestamp,
        )
        db.add(inference_meta)

        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(
                detail=(
                    f"Inference metadata already exists for dataset {dataset_id}. "
                    "Another request may have created it concurrently."
                )
            ) from exc

        from collections import defaultdict as dd

        image_map = dd(list)
        for img in uploaded_images:
            image_map[img.file_name].append(img)

        duplicates = {
            fname: len(imgs) for fname, imgs in image_map.items() if len(imgs) > 1
        }
        if duplicates:
            logger.warning("Found duplicate filenames in uploaded images: %s", duplicates)

        detections = []
        class_counts = defaultdict(
            lambda: {
                "count": 0,
                "sum_confidence": 0.0,
                "min_confidence": float("inf"),
                "max_confidence": float("-inf"),
                "image_ids": set(),
                "class_id": None,
            }
        )

        skipped_images = []

        for img_data in metadata_json.get("images", []):
            filename = img_data.get("filename", "")
            if filename not in image_map:
                skipped_images.append(filename)
                continue

            images_with_name = image_map[filename]
            if len(images_with_name) > 1:
                logger.warning(
                    "Multiple images found for filename '%s', using first match",
                    filename,
                )

            image_db = images_with_name[0]

            for det in img_data.get("detections", []):
                detection = ImageDetection(
                    image_id=image_db.id,
                    inference_metadata_id=inference_meta.id,
                    class_name=det.get("class", DEFAULT_CLASS_NAME),
                    class_id=det.get("class_id", DEFAULT_CLASS_ID),
                    confidence=det.get("confidence", DEFAULT_CONFIDENCE),
                    bbox_x1=det.get("bbox", {}).get("x1", DEFAULT_BBOX_COORD),
                    bbox_y1=det.get("bbox", {}).get("y1", DEFAULT_BBOX_COORD),
                    bbox_x2=det.get("bbox", {}).get("x2", DEFAULT_BBOX_COORD),
                    bbox_y2=det.get("bbox", {}).get("y2", DEFAULT_BBOX_COORD),
                )
                detections.append(detection)

                class_name = det.get("class", DEFAULT_CLASS_NAME)
                confidence = det.get("confidence", DEFAULT_CONFIDENCE)
                class_id = det.get("class_id", DEFAULT_CLASS_ID)

                existing_class_id = class_counts[class_name]["class_id"]
                if existing_class_id is not None and existing_class_id != class_id:
                    logger.warning(
                        "Class ID inconsistency detected: class '%s' has multiple IDs (%s, %s). "
                        "Using first occurrence: %s",
                        class_name,
                        existing_class_id,
                        class_id,
                        existing_class_id,
                    )
                elif existing_class_id is None:
                    class_counts[class_name]["class_id"] = class_id

                class_counts[class_name]["count"] += 1
                class_counts[class_name]["sum_confidence"] += confidence
                class_counts[class_name]["min_confidence"] = min(
                    class_counts[class_name]["min_confidence"], confidence
                )
                class_counts[class_name]["max_confidence"] = max(
                    class_counts[class_name]["max_confidence"], confidence
                )
                class_counts[class_name]["image_ids"].add(image_db.id)

        if skipped_images:
            logger.warning(
                "Skipped %s images not found in uploaded dataset: %s",
                len(skipped_images),
                skipped_images[:10],
            )

        if detections:
            for i in range(0, len(detections), BATCH_SIZE):
                batch = detections[i : i + BATCH_SIZE]
                db.add_all(batch)
                await db.flush()
        else:
            logger.warning("No detections found in metadata for dataset %s", dataset_id)

        class_stats = []
        for class_name, stats in class_counts.items():
            count = stats["count"]
            if count == 0:
                continue

            avg_conf = stats["sum_confidence"] / count
            min_conf = stats["min_confidence"]
            max_conf = stats["max_confidence"]

            from app.models.inference import DatasetClassStatistics

            stat = DatasetClassStatistics(
                dataset_id=dataset_id,
                class_name=class_name,
                class_id=stats["class_id"] or DEFAULT_CLASS_ID,
                detection_count=stats["count"],
                image_count=len(stats["image_ids"]),
                avg_confidence=avg_conf,
                min_confidence=min_conf,
                max_confidence=max_conf,
            )
            class_stats.append(stat)

        if class_stats:
            db.add_all(class_stats)

        inference_meta.total_images = len(metadata_json.get("images", []))
        inference_meta.total_detections = len(detections)
        await db.flush()

        class_distribution = {
            name: stats["count"] for name, stats in class_counts.items()
        }

        top_classes = sorted(
            class_distribution.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        return {
            "total_detections": len(detections),
            "total_images": len(metadata_json.get("images", [])),
            "class_distribution": class_distribution,
            "top_classes": [
                {"class": name, "count": count} for name, count in top_classes
            ],
        }


class DatasetUploadService:
    """Service for uploading and managing 2D datasets."""

    def __init__(
        self,
        *,
        storage=storage_manager,
        validator: Optional[DatasetUploadValidator] = None,
        folder_ingestor: Optional[DatasetFolderIngestor] = None,
        persistence_manager: Optional[DatasetPersistenceManager] = None,
        metadata_processor: Optional[InferenceMetadataProcessor] = None,
    ):
        self.storage = storage
        self._validator = validator or DatasetUploadValidator()
        self._folder_ingestor = folder_ingestor or DatasetFolderIngestor(self.storage)
        self._persistence_manager = persistence_manager or DatasetPersistenceManager()
        self._metadata_processor = metadata_processor or InferenceMetadataProcessor()

    async def upload_dataset_from_folder(
        self,
        db: AsyncSession,
        source_folder: str,
        dataset_name: str,
        description: Optional[str] = None,
        owner_id: Optional[UUID] = None,
        inference_metadata_path: Optional[str] = None,
    ) -> Tuple[Dataset2D, List[Image2D], Optional[Dict[str, Any]]]:
        logger.info("Starting dataset upload: %s from %s", dataset_name, source_folder)

        context = DatasetUploadContext(
            source_folder=source_folder,
            dataset_name=dataset_name,
            description=description,
            owner_id=owner_id,
            inference_metadata_path=inference_metadata_path,
        )

        metadata_path_obj = self._validator.validate_metadata_path(
            context.inference_metadata_path
        )

        ingestion = self._folder_ingestor.ingest(context)
        if not ingestion.image_list:
            self._folder_ingestor.cleanup(ingestion.storage_path)
            raise ValidationError(
                detail=(
                    "No images found in the source folder. Dataset must contain at least one image."
                )
            )

        try:
            dataset, images = await self._persistence_manager.create_dataset_records(
                db=db,
                context=context,
                ingestion=ingestion,
            )

            metadata_stats = None
            if metadata_path_obj:
                metadata_stats = await self._metadata_processor.process(
                    db=db,
                    dataset_id=dataset.id,
                    metadata_path=str(metadata_path_obj),
                    uploaded_images=images,
                )

            await db.commit()

            await db.refresh(dataset)
            for image in images:
                await db.refresh(image)

            return dataset, images, metadata_stats

        except (ValidationError, ConflictError, NotFoundError):
            await db.rollback()
            self._folder_ingestor.cleanup(ingestion.storage_path)
            raise
        except InternalServerError:
            await db.rollback()
            self._folder_ingestor.cleanup(ingestion.storage_path)
            raise
        except Exception as exc:
            await db.rollback()
            logger.error(
                "Upload failed, cleaning up storage at %s",
                ingestion.storage_path,
                exc_info=True,
            )
            self._folder_ingestor.cleanup(ingestion.storage_path)
            raise exc

    async def _process_inference_metadata_async(
        self,
        db: AsyncSession,
        dataset_id: UUID,
        metadata_path: str,
        uploaded_images: List[Image2D],
    ) -> Dict[str, Any]:
        """Backwards compatible wrapper for existing integrations."""
        return await self._metadata_processor.process(
            db=db,
            dataset_id=dataset_id,
            metadata_path=metadata_path,
            uploaded_images=uploaded_images,
        )


dataset_upload_service = DatasetUploadService()
