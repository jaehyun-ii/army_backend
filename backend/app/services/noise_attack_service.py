"""
Noise-based adversarial attack service (Plugin-based).
"""
import cv2
import json
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.plugins import attack_plugin_registry
from app.plugins.noise_2d_base import Noise2DConfig
from app.models.dataset_2d import AttackType
from app.services.attack_support import AttackLogger, resolve_target_class_id, resolve_image_path

import logging

logger = logging.getLogger(__name__)


@dataclass
class NoiseAttackContext:
    """Immutable request parameters for noise attack generation."""

    attack_name: str
    base_dataset_id: UUID
    plugin_name: str
    model_version_id: Optional[UUID]
    target_class: Optional[str]
    targeted: bool
    epsilon: Optional[float]
    alpha: Optional[float]
    iterations: Optional[int]
    mean: Optional[float]
    std: Optional[float]
    min_val: Optional[float]
    max_val: Optional[float]
    description: Optional[str]
    plugin_kwargs: Dict[str, Any]


@dataclass
class NoiseAttackResources:
    """Loaded artefacts required to execute a noise attack."""

    plugin: Any
    dataset: Any
    images: List[Any]
    model_version: Optional[Any]
    model: Optional[Any]
    target_class_id: Optional[int]


@dataclass
class NoiseAttackExecutionResult:
    """Execution summary for noise attack processing."""

    processed_count: int
    failed_count: int
    skipped_count: int
    noise_stats: List[Dict[str, float]]
    attack_results: List[Dict[str, Any]]


class NoiseAttackResourceLoader:
    """Load plugins, datasets, and optional models for noise attacks."""

    async def load(
        self,
        db: AsyncSession,
        context: NoiseAttackContext,
        generation_logger: AttackLogger,
    ) -> NoiseAttackResources:
        await generation_logger.status("Loading attack plugin...")
        plugin = attack_plugin_registry.get_plugin(context.plugin_name)
        if not plugin:
            raise ValueError(
                f"Plugin '{context.plugin_name}' not found. "
                f"Available plugins: {list(attack_plugin_registry._plugins.keys())}"
            )

        await generation_logger.status(f"Loading base dataset {context.base_dataset_id}...")
        dataset = await crud.dataset_2d.get(db, id=context.base_dataset_id)
        if not dataset:
            raise ValueError(f"Base dataset {context.base_dataset_id} not found")

        images = await crud.image_2d.get_by_dataset(db, dataset_id=context.base_dataset_id)
        if not images:
            raise ValueError(f"No images in dataset {context.base_dataset_id}")

        await generation_logger.info(
            f"Loaded {len(images)} images from dataset",
            image_count=len(images),
        )

        model_version = None
        target_class_id = None
        model = None

        if plugin.requires_model:
            if not context.model_version_id:
                raise ValueError(f"Plugin '{context.plugin_name}' requires model_version_id")

            await generation_logger.status("Loading model for gradient-based attack...")
            model_version = await crud.od_model_version.get(db, id=context.model_version_id)
            if not model_version:
                raise ValueError(f"Model version {context.model_version_id} not found")

            if context.targeted and context.target_class:
                if not model_version.labelmap:
                    raise ValueError(f"Model version {context.model_version_id} has no labelmap")
                target_class_id = resolve_target_class_id(
                    model_version.labelmap,
                    context.target_class,
                )

            model = await self._load_model(
                model_version_id=context.model_version_id,
                generation_logger=generation_logger,
            )

        return NoiseAttackResources(
            plugin=plugin,
            dataset=dataset,
            images=images,
            model_version=model_version,
            model=model,
            target_class_id=target_class_id,
        )

    async def _load_model(
        self,
        model_version_id: UUID,
        generation_logger: AttackLogger,
    ) -> Any:
        """Load detector model for gradient-based attacks."""
        try:
            from app.ai.model_loader import model_loader

            if str(model_version_id) not in model_loader.loaded_models:
                logger.info(f"Loading model {model_version_id}...")
                model_loader.load_model(str(model_version_id))

            detector = model_loader.loaded_models[str(model_version_id)]
            if not hasattr(detector, "model") or detector.model is None:
                raise ValueError("Detector does not have a valid model attribute")

            await generation_logger.info(f"Loaded model {model_version_id}")
            return detector.model
        except Exception as exc:
            import traceback

            logger.error(f"Failed to load model {model_version_id}: {exc}")
            logger.error(traceback.format_exc())
            raise ValueError(f"Failed to load model for attack: {exc}") from exc


class NoiseAttackExecutor:
    """Execute noise attack generation across dataset images."""

    def __init__(self, storage_root: Path):
        self._storage_root = storage_root

    async def execute(
        self,
        context: NoiseAttackContext,
        resources: NoiseAttackResources,
        config: Noise2DConfig,
        attack_dir: Path,
        generation_logger: AttackLogger,
    ) -> NoiseAttackExecutionResult:
        total_images = len(resources.images)
        await generation_logger.status(
            f"Processing {total_images} images with {context.plugin_name} attack...",
            total_images=total_images,
        )

        processed = failed = skipped = 0
        noise_stats: List[Dict[str, float]] = []
        attack_results: List[Dict[str, Any]] = []

        for idx, image_record in enumerate(resources.images):
            try:
                await generation_logger.progress(
                    f"[{idx + 1}/{total_images}] Processing {image_record.file_name}...",
                    current=idx + 1,
                    total=total_images,
                )

                img_path, orig_img = await self._load_original_image(
                    image_record,
                    generation_logger,
                )
                if orig_img is None:
                    failed += 1
                    continue

                bboxes = await self._determine_bboxes(
                    image_record=image_record,
                    original_image=orig_img,
                    context=context,
                    generation_logger=generation_logger,
                )

                if context.targeted and context.target_class and not bboxes:
                    await generation_logger.warning(
                        f"Skipped {image_record.file_name}: no '{context.target_class}' objects found"
                    )
                    skipped += 1
                    continue

                noisy_img, stats = await self._generate_noisy_image(
                    orig_img=orig_img,
                    bboxes=bboxes,
                    config=config,
                    resources=resources,
                )

                result_entry = await self._save_attack_output(
                    img_path=img_path,
                    noisy_image=noisy_img,
                    attack_dir=attack_dir,
                    stats=stats,
                    generation_logger=generation_logger,
                )

                noise_stats.append(stats)
                attack_results.append(result_entry)
                processed += 1

                if (idx + 1) % 5 == 0 or (idx + 1) == total_images:
                    await self._log_batch_progress(
                        generation_logger=generation_logger,
                        idx=idx,
                        total=total_images,
                        processed=processed,
                        failed=failed,
                        skipped=skipped,
                    )

            except Exception as exc:
                import traceback

                logger.error("Error processing image %s: %s", image_record.file_name, exc)
                logger.error(traceback.format_exc())
                await generation_logger.error(
                    f"Failed to process {image_record.file_name}: {exc}"
                )
                failed += 1

        return NoiseAttackExecutionResult(
            processed_count=processed,
            failed_count=failed,
            skipped_count=skipped,
            noise_stats=noise_stats,
            attack_results=attack_results,
        )

    async def _load_original_image(
        self,
        image_record: Any,
        generation_logger: AttackLogger,
    ) -> Tuple[Path, Optional[np.ndarray]]:
        img_path = resolve_image_path(self._storage_root, image_record.storage_key)
        if not img_path.exists():
            await generation_logger.warning(f"Image not found: {img_path}")
            return img_path, None

        orig_img = cv2.imread(str(img_path))
        if orig_img is None:
            await generation_logger.warning(f"Failed to load image: {img_path}")
            return img_path, None

        return img_path, orig_img

    async def _determine_bboxes(
        self,
        image_record: Any,
        original_image: np.ndarray,
        context: NoiseAttackContext,
        generation_logger: AttackLogger,
    ) -> List[List[float]]:
        bboxes, metadata_message = self._collect_metadata_bboxes(
            image_record,
            context.target_class,
        )
        if metadata_message:
            await generation_logger.info(metadata_message)

        if not bboxes and context.target_class and context.model_version_id:
            return await self._collect_inference_bboxes(
                image=original_image,
                context=context,
                generation_logger=generation_logger,
            )

        if context.target_class and context.targeted and not context.model_version_id:
            await generation_logger.warning(
                "Targeted attack requested but no model_version_id provided; skipping detection."
            )
        return bboxes

    async def _generate_noisy_image(
        self,
        orig_img: np.ndarray,
        bboxes: List[List[float]],
        config: Noise2DConfig,
        resources: NoiseAttackResources,
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        noise = await resources.plugin.generate_noise(
            image=orig_img,
            config=config,
            model=resources.model,
            target_class_id=resources.target_class_id,
            bboxes=bboxes,
        )

        noisy_img = await resources.plugin.apply_noise(
            image=orig_img,
            noise=noise,
            config=config,
            bboxes=bboxes if bboxes else None,
        )

        stats = await resources.plugin.compute_noise_stats(noise)
        return noisy_img, stats

    async def _save_attack_output(
        self,
        img_path: Path,
        noisy_image: np.ndarray,
        attack_dir: Path,
        stats: Dict[str, float],
        generation_logger: AttackLogger,
    ) -> Dict[str, Any]:
        output_filename = f"noise_{img_path.stem}.jpg"
        output_path = attack_dir / output_filename
        cv2.imwrite(str(output_path), noisy_image)
        await generation_logger.info(f"Saved attacked image: {output_filename}")

        return {
            "original_filename": img_path.name,
            "attacked_filename": output_filename,
            "noise_stats": stats,
        }

    async def _log_batch_progress(
        self,
        generation_logger: AttackLogger,
        idx: int,
        total: int,
        processed: int,
        failed: int,
        skipped: int,
    ) -> None:
        await generation_logger.progress(
            f"Processed {idx + 1}/{total} images...",
            current=idx + 1,
            total=total,
            processed=processed,
            failed=failed,
            skipped=skipped,
        )

    def _collect_metadata_bboxes(
        self,
        image_record: Any,
        target_class: Optional[str],
    ) -> Tuple[List[List[float]], Optional[str]]:
        """Extract bounding boxes for the target class from image metadata."""
        if not target_class or not image_record.metadata_:
            return [], None

        if not isinstance(image_record.metadata_, dict):
            return [], None

        metadata = image_record.metadata_
        bboxes: List[List[float]] = []
        message: Optional[str] = None

        if metadata.get("class") == target_class and "bbox" in metadata:
            bbox = metadata["bbox"]
            bboxes.append([
                float(bbox.get("x1", 0)),
                float(bbox.get("y1", 0)),
                float(bbox.get("x2", 0)),
                float(bbox.get("y2", 0)),
            ])
            message = f"Using bbox from metadata for '{target_class}'"
            return bboxes, message

        annotations = metadata.get("annotations")
        if isinstance(annotations, list):
            for ann in annotations:
                if ann.get("class") == target_class or ann.get("class_name") == target_class:
                    bbox = ann.get("bbox")
                    if bbox:
                        bboxes.append([
                            float(bbox.get("x1", 0)),
                            float(bbox.get("y1", 0)),
                            float(bbox.get("x2", 0)),
                            float(bbox.get("y2", 0)),
                        ])
            if bboxes:
                message = f"Using {len(bboxes)} bbox(es) from metadata for '{target_class}'"
                return bboxes, message

        if "bbox" in metadata:
            bbox = metadata["bbox"]
            bboxes.append([
                float(bbox.get("x1", 0)),
                float(bbox.get("y1", 0)),
                float(bbox.get("x2", 0)),
                float(bbox.get("y2", 0)),
            ])
            message = f"Using bbox from metadata for '{target_class}'"

        return bboxes, message

    async def _collect_inference_bboxes(
        self,
        image: Any,
        context: NoiseAttackContext,
        generation_logger: AttackLogger,
    ) -> List[List[float]]:
        """Run model inference to derive target class bounding boxes."""
        if not context.model_version_id or not context.target_class:
            return []

        await generation_logger.info(
            f"Running inference to detect '{context.target_class}' instances..."
        )

        from app.services.custom_model_service import custom_model_service

        result = await custom_model_service.run_inference(
            version_id=str(context.model_version_id),
            image=image,
            conf_threshold=0.25,
        )

        boxes: List[List[float]] = []
        for det in result.detections:
            if det.class_name == context.target_class:
                boxes.append([det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2])

        await generation_logger.info(
            f"Found {len(boxes)} '{context.target_class}' instances via inference"
        )
        return boxes


class NoiseAttackPersistenceManager:
    """Persist noise attack artefacts and metadata."""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def create_attack_dir(self, attack_name: str) -> Path:
        attack_dir = self._base_dir / f"{attack_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        attack_dir.mkdir(parents=True, exist_ok=True)
        return attack_dir

    async def persist(
        self,
        db: AsyncSession,
        context: NoiseAttackContext,
        resources: NoiseAttackResources,
        config: Noise2DConfig,
        attack_dir: Path,
        execution_result: NoiseAttackExecutionResult,
    ) -> Tuple[Any, Dict[str, float]]:
        from app.schemas.dataset_2d import AttackDataset2DCreate

        if execution_result.noise_stats:
            avg_noise_mag = float(np.mean([s["avg_magnitude"] for s in execution_result.noise_stats]))
            max_noise_mag = float(max([s["max_magnitude"] for s in execution_result.noise_stats]))
        else:
            avg_noise_mag = 0.0
            max_noise_mag = 0.0

        parameters = {
            "plugin_name": context.plugin_name,
            "epsilon": context.epsilon,
            "alpha": context.alpha,
            "iterations": context.iterations,
            "mean": context.mean,
            "std": context.std,
            "min_val": context.min_val,
            "max_val": context.max_val,
            "targeted": context.targeted,
            "storage_path": str(attack_dir),
            "processed_images": execution_result.processed_count,
            "failed_images": execution_result.failed_count,
            "skipped_images": execution_result.skipped_count,
            "avg_noise_magnitude": avg_noise_mag,
            "max_noise_magnitude": max_noise_mag,
            "attack_results": execution_result.attack_results,
        }
        if context.plugin_kwargs:
            parameters.update(context.plugin_kwargs)

        attack_data = AttackDataset2DCreate(
            name=context.attack_name,
            description=context.description,
            attack_type=AttackType.NOISE,
            target_class=context.target_class,
            target_model_version_id=context.model_version_id,
            base_dataset_id=context.base_dataset_id,
            parameters=parameters,
        )

        attack_dataset_db = await crud.attack_dataset_2d.create(db, obj_in=attack_data)

        metadata_file = attack_dir / "attack_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump({
                "attack_dataset_id": str(attack_dataset_db.id),
                "attack_dataset_name": context.attack_name,
                "plugin_name": context.plugin_name,
                "plugin_info": resources.plugin.get_info(),
                "base_dataset_id": str(context.base_dataset_id),
                "model_version_id": str(context.model_version_id) if context.model_version_id else None,
                "target_class": context.target_class,
                "targeted": context.targeted,
                "parameters": {
                    "epsilon": context.epsilon,
                    "alpha": context.alpha,
                    "iterations": context.iterations,
                    "mean": context.mean,
                    "std": context.std,
                    "min_val": context.min_val,
                    "max_val": context.max_val,
                },
                "statistics": {
                    "total_images": len(resources.images),
                    "processed_images": execution_result.processed_count,
                    "skipped_images": execution_result.skipped_count,
                    "failed_images": execution_result.failed_count,
                    "avg_noise_magnitude": avg_noise_mag,
                    "max_noise_magnitude": max_noise_mag,
                },
                "created_at": datetime.now().isoformat(),
                "results": execution_result.attack_results,
            }, f, indent=2)

        return attack_dataset_db, {
            "avg_noise_magnitude": avg_noise_mag,
            "max_noise_magnitude": max_noise_mag,
        }


class NoiseAttackService:
    """Service for noise-based adversarial attacks using plugin system."""

    def __init__(self):
        self.storage_root = Path(settings.STORAGE_ROOT)
        self.noise_attacks_dir = self.storage_root / "noise_attacks"
        self.noise_attacks_dir.mkdir(parents=True, exist_ok=True)

        self._resource_loader = NoiseAttackResourceLoader()
        self._executor = NoiseAttackExecutor(self.storage_root)
        self._persistence_manager = NoiseAttackPersistenceManager(self.noise_attacks_dir)

    async def generate_noise_attack_dataset(
        self,
        db: AsyncSession,
        attack_name: str,
        base_dataset_id: UUID,
        plugin_name: str,
        model_version_id: Optional[UUID] = None,
        target_class: Optional[str] = None,
        epsilon: Optional[float] = None,
        alpha: Optional[float] = None,
        iterations: Optional[int] = None,
        mean: Optional[float] = None,
        std: Optional[float] = None,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        targeted: bool = False,
        description: Optional[str] = None,
        created_by: Optional[UUID] = None,  # Reserved for future use
        session_id: Optional[str] = None,
        sse_manager: Optional[Any] = None,
        **plugin_kwargs: Any,
    ) -> Tuple[Any, Path]:
        """
        Generate noise attack dataset using specified plugin.

        Returns:
            Tuple of (attack_dataset_db_object, attack_dataset_dir_path)
        """
        generation_logger = AttackLogger(logger, sse_manager, session_id)
        context = NoiseAttackContext(
            attack_name=attack_name,
            base_dataset_id=base_dataset_id,
            plugin_name=plugin_name,
            model_version_id=model_version_id,
            target_class=target_class,
            targeted=targeted,
            epsilon=epsilon,
            alpha=alpha,
            iterations=iterations,
            mean=mean,
            std=std,
            min_val=min_val,
            max_val=max_val,
            description=description,
            plugin_kwargs=dict(plugin_kwargs),
        )

        await generation_logger.status(
            f"Starting noise attack generation using plugin: {plugin_name}"
        )

        resources = await self._resource_loader.load(db, context, generation_logger)

        config = Noise2DConfig(
            name=context.attack_name,
            description=context.description,
            base_dataset_id=str(context.base_dataset_id),
            output_dataset_name=context.attack_name,
            model_version_id=str(context.model_version_id) if context.model_version_id else None,
            target_class=context.target_class,
            targeted=context.targeted,
            epsilon=context.epsilon,
            alpha=context.alpha,
            iterations=context.iterations,
            mean=context.mean,
            std=context.std,
            min_val=context.min_val,
            max_val=context.max_val,
            **context.plugin_kwargs,
        )

        await resources.plugin.validate_config(config)

        attack_dir = self._persistence_manager.create_attack_dir(context.attack_name)

        execution_result = await self._executor.execute(
            context=context,
            resources=resources,
            config=config,
            attack_dir=attack_dir,
            generation_logger=generation_logger,
        )

        attack_dataset_db, aggregate_stats = await self._persistence_manager.persist(
            db=db,
            context=context,
            resources=resources,
            config=config,
            attack_dir=attack_dir,
            execution_result=execution_result,
        )

        await generation_logger.success(
            "Noise attack dataset created successfully!",
            attack_dataset_id=str(attack_dataset_db.id),
            processed_images=execution_result.processed_count,
            skipped_images=execution_result.skipped_count,
            failed_images=execution_result.failed_count,
            avg_noise_magnitude=aggregate_stats["avg_noise_magnitude"],
            storage_path=str(attack_dir),
        )

        logger.info(
            "Noise attack dataset generated using %s: %s processed, %s skipped, %s failed",
            context.plugin_name,
            execution_result.processed_count,
            execution_result.skipped_count,
            execution_result.failed_count,
        )

        return attack_dataset_db, attack_dir


# Global instance
noise_attack_service = NoiseAttackService()
