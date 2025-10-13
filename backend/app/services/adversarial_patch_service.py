"""
Adversarial patch generation and application service (Plugin-based).
"""
import cv2
import numpy as np
import json
import tempfile
import shutil
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.plugins import attack_plugin_registry
from app.plugins.patch_2d_base import Patch2DConfig
from app.services.attack_support import (
    AttackLogger,
    resolve_target_class_id,
    resolve_image_path,
)

logger = logging.getLogger(__name__)


@dataclass
class PatchRequestContext:
    """Immutable request details used during generation."""

    patch_name: str
    model_version_id: UUID
    dataset_id: UUID
    target_class: str
    plugin_name: str
    patch_size: int
    area_ratio: float
    epsilon: float
    alpha: float
    iterations: int
    batch_size: int
    description: Optional[str]
    plugin_kwargs: Dict[str, Any]


@dataclass
class PatchResources:
    """Loaded resources required for patch generation."""

    plugin: Any
    images: List[Any]
    model_version: Any
    weights_path: Path
    target_class_id: int


class PatchResourceLoader:
    """Load plugins, datasets, and model artefacts required for generation."""

    def __init__(self, storage_root: Path):
        self._storage_root = storage_root

    async def load(
        self,
        db: AsyncSession,
        context: PatchRequestContext,
        generation_logger: AttackLogger,
    ) -> PatchResources:
        await generation_logger.status("Loading attack plugin...")
        plugin = attack_plugin_registry.get_plugin(context.plugin_name)
        if not plugin:
            raise ValueError(
                f"Plugin '{context.plugin_name}' not found. "
                f"Available plugins: {list(attack_plugin_registry._plugins.keys())}"
            )

        await generation_logger.status(f"Loading dataset {context.dataset_id}...")
        dataset = await crud.dataset_2d.get(db, id=context.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {context.dataset_id} not found")

        images = await crud.image_2d.get_by_dataset(db, dataset_id=context.dataset_id)
        if not images:
            raise ValueError(f"No images found in dataset {context.dataset_id}")
        await generation_logger.info(
            f"Loaded {len(images)} images from dataset", image_count=len(images)
        )

        await generation_logger.status(f"Loading model version {context.model_version_id}...")
        model_version = await crud.od_model_version.get(db, id=context.model_version_id)
        if not model_version:
            raise ValueError(f"Model version {context.model_version_id} not found")

        if not model_version.labelmap:
            raise ValueError(f"Model version {context.model_version_id} has no labelmap")

        target_class_id = resolve_target_class_id(
            model_version.labelmap, context.target_class
        )

        artifacts = await crud.od_model_artifact.get_by_version(
            db, version_id=context.model_version_id
        )
        weights_artifact = next((a for a in artifacts if (
            a.artifact_type == "weights" or
            (hasattr(a.artifact_type, "value") and a.artifact_type.value == "weights")
        )), None)
        if not weights_artifact:
            raise ValueError(f"No weights found for model version {context.model_version_id}")

        weights_path = (
            self._storage_root / "custom_models" / str(context.model_version_id) / weights_artifact.file_name
        )

        return PatchResources(
            plugin=plugin,
            images=images,
            model_version=model_version,
            weights_path=weights_path,
            target_class_id=target_class_id,
        )

class PatchInferenceCollector:
    """Run inference across dataset images to locate target class instances."""

    def __init__(self, storage_root: Path):
        self._storage_root = storage_root

    async def collect(
        self,
        images: List[Any],
        model_version_id: UUID,
        target_class: str,
        generation_logger: AttackLogger,
    ) -> List[Tuple[Path, List[float]]]:
        await generation_logger.status(
            f"Running inference on {len(images)} images to find '{target_class}' instances...",
            total_images=len(images)
        )
        from app.services.custom_model_service import custom_model_service

        image_bbox_list: List[Tuple[Path, List[float]]] = []
        for idx, img in enumerate(images):
            img_path = resolve_image_path(self._storage_root, img.storage_key)
            if not img_path.exists():
                logger.warning(f"Image file not found: {img_path}")
                continue

            img_cv = cv2.imread(str(img_path))
            if img_cv is None:
                logger.warning(f"Failed to load image with cv2: {img_path}")
                continue

            result = await custom_model_service.run_inference(
                version_id=str(model_version_id),
                image=img_cv,
                conf_threshold=0.25
            )

            for det in result.detections:
                if det.class_name == target_class:
                    bbox = [
                        det.bbox.x1,
                        det.bbox.y1,
                        det.bbox.x2,
                        det.bbox.y2
                    ]
                    image_bbox_list.append((img_path, bbox))

            if (idx + 1) % 10 == 0:
                await generation_logger.progress(
                    f"Processed {idx + 1}/{len(images)} images...",
                    processed=idx + 1,
                    total=len(images)
                )

        await generation_logger.info(
            f"Found {len(image_bbox_list)} '{target_class}' instances in {len(images)} images",
            instances_found=len(image_bbox_list),
        )

        if not image_bbox_list:
            raise ValueError(f"No {target_class} objects found in dataset")

        return image_bbox_list

class PatchGenerator:
    """Generate adversarial patches via plugins."""

    async def run(
        self,
        plugin: Any,
        config: Patch2DConfig,
        weights_path: Path,
        image_bbox_list: List[Tuple[Path, List[float]]],
        target_class_id: int,
        generation_logger: AttackLogger,
    ) -> Tuple[np.ndarray, float]:
        await generation_logger.status(
            f"Starting patch generation with {config.iterations} iterations...",
            iterations=config.iterations,
            batch_size=config.batch_size,
        )
        patch_np, best_score = await plugin.generate_patch(
            model_path=weights_path,
            image_bbox_list=image_bbox_list,
            target_class_id=target_class_id,
            config=config
        )
        return patch_np, float(best_score)


class PatchPersistenceManager:
    """Persist generated patch artefacts and metadata."""

    def __init__(self, patches_dir: Path):
        self._patches_dir = patches_dir

    async def persist(
        self,
        db: AsyncSession,
        context: PatchRequestContext,
        resources: PatchResources,
        image_bbox_list: List[Tuple[Path, List[float]]],
        patch_np: np.ndarray,
        best_score: float,
        generation_logger: AttackLogger,
    ) -> Tuple[Any, Path]:
        await generation_logger.status("Saving generated patch to storage...")
        patch_path = self._save_patch_file(context.patch_name, patch_np)

        await generation_logger.status("Creating patch record in database...")
        from app.schemas.dataset_2d import Patch2DCreate

        patch_data = Patch2DCreate(
            name=context.patch_name,
            description=context.description,
            target_class=context.target_class,
            method=f"{resources.plugin.name} v{resources.plugin.version}",
            target_model_version_id=context.model_version_id,
            source_dataset_id=context.dataset_id,
            hyperparameters={
                "plugin_name": context.plugin_name,
                "patch_size": context.patch_size,
                "area_ratio": context.area_ratio,
                "epsilon": context.epsilon,
                "alpha": context.alpha,
                "iterations": context.iterations,
                "batch_size": context.batch_size,
                **context.plugin_kwargs,
            },
            patch_metadata={
                "patch_file": str(patch_path),
                "target_class_id": resources.target_class_id,
                "best_score": best_score,
                "num_training_samples": len(image_bbox_list),
                "plugin_info": resources.plugin.get_info(),
            },
        )

        patch_db = await crud.patch_2d.create(db, obj_in=patch_data)

        await generation_logger.success(
            "Patch generation completed successfully!",
            patch_id=str(patch_db.id),
            best_score=best_score,
            patch_file=str(patch_path),
        )

        return patch_db, patch_path

    def _save_patch_file(self, patch_name: str, patch_np: np.ndarray) -> Path:
        """Save patch image to disk."""
        patch_filename = f"{patch_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        patch_path = self._patches_dir / patch_filename
        cv2.imwrite(str(patch_path), cv2.cvtColor(patch_np, cv2.COLOR_RGB2BGR))
        return patch_path


class AttackDatasetExporter:
    """Create downloadable archives for attack datasets."""

    def create_archive(self, storage_path: str, dataset_name: str) -> Path:
        export_dir = Path(storage_path)
        if not export_dir.exists():
            raise ValueError("Attack dataset storage path not found")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            archive_path = Path(tmp.name)

        shutil.make_archive(
            archive_path.with_suffix(""),
            "zip",
            storage_path,
        )
        return archive_path

    def cleanup_archive(self, archive_path: Path) -> None:
        archive_path = Path(archive_path)
        if archive_path.exists():
            try:
                archive_path.unlink()
            except Exception:
                logger.warning(
                    "Failed to cleanup archive %s", archive_path, exc_info=True
                )


class AdversarialPatchService:
    """
    Service for generating and applying adversarial patches using plugin system.

    SOLID Improvements:
    - SRP: Delegates to specialized components (loader, collector, generator, etc.)
    - DIP: Components injected as dependencies
    - OCP: Plugin-based extensibility
    """

    def __init__(
        self,
        *,
        storage_root: Optional[Path] = None,
        resource_loader: Optional[PatchResourceLoader] = None,
        inference_collector: Optional[PatchInferenceCollector] = None,
        patch_generator: Optional[PatchGenerator] = None,
        persistence_manager: Optional[PatchPersistenceManager] = None,
        dataset_exporter: Optional[AttackDatasetExporter] = None,
    ):
        """
        Initialize patch service with dependency injection.

        Args:
            storage_root: Root storage path (defaults to settings.STORAGE_ROOT)
            resource_loader: Component for loading resources (DI)
            inference_collector: Component for collecting inferences (DI)
            patch_generator: Component for generating patches (DI)
            persistence_manager: Component for persisting patches (DI)
            dataset_exporter: Component for exporting datasets (DI)
        """
        self.storage_root = storage_root or Path(settings.STORAGE_ROOT)
        self.patches_dir = self.storage_root / "patches"
        self.attack_datasets_dir = self.storage_root / "attack_datasets"

        # Create directories
        self.patches_dir.mkdir(parents=True, exist_ok=True)
        self.attack_datasets_dir.mkdir(parents=True, exist_ok=True)

        # Inject dependencies (DIP pattern)
        self._resource_loader = resource_loader or PatchResourceLoader(self.storage_root)
        self._inference_collector = inference_collector or PatchInferenceCollector(self.storage_root)
        self._patch_generator = patch_generator or PatchGenerator()
        self._persistence_manager = persistence_manager or PatchPersistenceManager(self.patches_dir)
        self._dataset_exporter = dataset_exporter or AttackDatasetExporter()

    async def generate_patch(
        self,
        db: AsyncSession,
        patch_name: str,
        model_version_id: UUID,
        dataset_id: UUID,
        target_class: str,
        plugin_name: str = settings.DEFAULT_PATCH_PLUGIN,
        patch_size: int = 100,
        area_ratio: float = 0.3,
        epsilon: float = 0.6,
        alpha: float = 0.03,
        iterations: int = 100,
        batch_size: int = 8,
        description: Optional[str] = None,
        created_by: Optional[UUID] = None,
        sse_manager: Optional[Any] = None,
        session_id: Optional[str] = None,
        **plugin_kwargs
    ) -> Tuple[Any, Path]:
        """
        Generate adversarial patch using specified plugin.

        Args:
            db: Database session
            patch_name: Name for the patch
            model_version_id: Model version to attack
            dataset_id: Source dataset ID
            target_class: Target class name (e.g., "person", "car")
            plugin_name: Name of the patch generation plugin (default: "global_pgd_2d")
            patch_size: Base patch size
            area_ratio: Patch area ratio relative to bbox
            epsilon: Perturbation budget
            alpha: Learning rate
            iterations: Number of iterations
            batch_size: Batch size for training
            description: Optional description
            created_by: Optional user ID
            **plugin_kwargs: Additional plugin-specific parameters

        Returns:
            Tuple of (patch_db_object, patch_file_path)
        """
        generation_logger = AttackLogger(logger, sse_manager, session_id)
        context = PatchRequestContext(
            patch_name=patch_name,
            model_version_id=model_version_id,
            dataset_id=dataset_id,
            target_class=target_class,
            plugin_name=plugin_name,
            patch_size=patch_size,
            area_ratio=area_ratio,
            epsilon=epsilon,
            alpha=alpha,
            iterations=iterations,
            batch_size=batch_size,
            description=description,
            plugin_kwargs=plugin_kwargs,
        )

        await generation_logger.status(f"Starting patch generation using plugin: {plugin_name}")

        resources = await self._resource_loader.load(db, context, generation_logger)
        image_bbox_list = await self._inference_collector.collect(
            resources.images,
            model_version_id,
            target_class,
            generation_logger,
        )

        config = Patch2DConfig(
            name=context.patch_name,
            description=context.description,
            base_dataset_id=str(context.dataset_id),
            output_dataset_name=context.patch_name,
            model_version_id=str(context.model_version_id),
            target_class=context.target_class,
            targeted=True,
            patch_size=context.patch_size,
            area_ratio=context.area_ratio,
            epsilon=context.epsilon,
            alpha=context.alpha,
            iterations=context.iterations,
            batch_size=context.batch_size,
            **context.plugin_kwargs,
        )

        await resources.plugin.validate_config(config)

        patch_np, best_score = await self._patch_generator.run(
            resources.plugin,
            config,
            resources.weights_path,
            image_bbox_list,
            resources.target_class_id,
            generation_logger,
        )

        patch_db, patch_path = await self._persistence_manager.persist(
            db=db,
            context=context,
            resources=resources,
            image_bbox_list=image_bbox_list,
            patch_np=patch_np,
            best_score=best_score,
            generation_logger=generation_logger,
        )

        return patch_db, patch_path

    async def apply_patch_to_dataset(
        self,
        db: AsyncSession,
        attack_dataset_name: str,
        model_version_id: UUID,
        base_dataset_id: UUID,
        patch_id: UUID,
        target_class: str,
        patch_scale: float = 0.3,
        description: Optional[str] = None,
        created_by: Optional[UUID] = None,
    ) -> Tuple[Any, Path]:
        """
        Apply adversarial patch to all images in dataset.
        """
        patch, patch_rgb = await self._load_patch_assets(db, patch_id)
        base_dataset, images = await self._load_dataset_images(db, base_dataset_id)
        attack_dir = self._create_attack_directory(attack_dataset_name)

        attack_results, processed_count = await self._apply_patch_to_images(
            images=images,
            model_version_id=model_version_id,
            target_class=target_class,
            patch_rgb=patch_rgb,
            patch_scale=patch_scale,
            attack_dir=attack_dir,
        )

        attack_dataset_db = await self._record_patch_attack(
            db=db,
            attack_dataset_name=attack_dataset_name,
            model_version_id=model_version_id,
            base_dataset_id=base_dataset.id,
            patch_id=patch.id,
            target_class=target_class,
            patch_scale=patch_scale,
            description=description,
            processed_count=processed_count,
            attack_results=attack_results,
            attack_dir=attack_dir,
        )

        self._write_attack_metadata(
            attack_dataset_db=attack_dataset_db,
            attack_dataset_name=attack_dataset_name,
            model_version_id=model_version_id,
            base_dataset_id=base_dataset_id,
            patch_id=patch_id,
            target_class=target_class,
            patch_scale=patch_scale,
            processed_count=processed_count,
            attack_results=attack_results,
            attack_dir=attack_dir,
        )

        return attack_dataset_db, attack_dir

    async def _load_patch_assets(
        self,
        db: AsyncSession,
        patch_id: UUID,
    ) -> Tuple[Any, np.ndarray]:
        patch = await crud.patch_2d.get(db, id=patch_id)
        if not patch:
            raise ValueError(f"Patch {patch_id} not found")

        patch_file = patch.patch_metadata.get("patch_file")
        if not patch_file or not Path(patch_file).exists():
            raise ValueError(f"Patch file not found: {patch_file}")

        patch_img = cv2.imread(patch_file)
        patch_rgb = cv2.cvtColor(patch_img, cv2.COLOR_BGR2RGB)
        return patch, patch_rgb

    async def _load_dataset_images(
        self,
        db: AsyncSession,
        base_dataset_id: UUID,
    ) -> Tuple[Any, List[Any]]:
        base_dataset = await crud.dataset_2d.get(db, id=base_dataset_id)
        if not base_dataset:
            raise ValueError(f"Base dataset {base_dataset_id} not found")

        images = await crud.image_2d.get_by_dataset(db, dataset_id=base_dataset_id)
        if not images:
            raise ValueError(f"No images in dataset {base_dataset_id}")
        return base_dataset, images

    def _create_attack_directory(self, attack_dataset_name: str) -> Path:
        attack_dir = (
            self.attack_datasets_dir
            / f"{attack_dataset_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        attack_dir.mkdir(parents=True, exist_ok=True)
        return attack_dir

    async def _apply_patch_to_images(
        self,
        images: List[Any],
        model_version_id: UUID,
        target_class: str,
        patch_rgb: np.ndarray,
        patch_scale: float,
        attack_dir: Path,
    ) -> Tuple[List[Dict[str, Any]], int]:
        from app.services.custom_model_service import custom_model_service

        attack_results: List[Dict[str, Any]] = []
        processed_count = 0

        for image_record in images:
            result = await self._apply_patch_to_image(
                image_record=image_record,
                model_version_id=model_version_id,
                target_class=target_class,
                patch_rgb=patch_rgb,
                patch_scale=patch_scale,
                attack_dir=attack_dir,
                custom_model_service=custom_model_service,
            )
            if result:
                attack_results.append(result)
                processed_count += 1

        return attack_results, processed_count

    async def _apply_patch_to_image(
        self,
        image_record: Any,
        model_version_id: UUID,
        target_class: str,
        patch_rgb: np.ndarray,
        patch_scale: float,
        attack_dir: Path,
        custom_model_service,
    ) -> Optional[Dict[str, Any]]:
        img_path = Path(image_record.storage_key)
        if not img_path.exists():
            return None

        orig_img = cv2.imread(str(img_path))
        if orig_img is None:
            return None

        inference_result = await custom_model_service.run_inference(
            version_id=str(model_version_id),
            image=orig_img,
            conf_threshold=0.25,
        )

        orig_rgb = cv2.cvtColor(orig_img, cv2.COLOR_BGR2RGB)
        modified = False

        for det in inference_result.detections:
            if det.class_name != target_class:
                continue

            bbox_w = det.bbox.x2 - det.bbox.x1
            target_patch_size = max(int(bbox_w * patch_scale), 10)
            if target_patch_size <= 0:
                continue

            patch_resized = cv2.resize(patch_rgb, (target_patch_size, target_patch_size))

            center_x = int((det.bbox.x1 + det.bbox.x2) / 2)
            center_y = int((det.bbox.y1 + det.bbox.y2) / 2)

            patch_x1 = max(0, center_x - target_patch_size // 2)
            patch_y1 = max(0, center_y - target_patch_size // 2)
            patch_x2 = min(orig_rgb.shape[1], patch_x1 + target_patch_size)
            patch_y2 = min(orig_rgb.shape[0], patch_y1 + target_patch_size)

            actual_w = patch_x2 - patch_x1
            actual_h = patch_y2 - patch_y1
            if actual_w <= 0 or actual_h <= 0:
                continue

            orig_rgb[patch_y1:patch_y2, patch_x1:patch_x2] = patch_resized[
                :actual_h, :actual_w
            ]
            modified = True

        if not modified:
            return None

        output_filename = f"attacked_{img_path.stem}.jpg"
        output_path = attack_dir / output_filename
        cv2.imwrite(str(output_path), cv2.cvtColor(orig_rgb, cv2.COLOR_RGB2BGR))

        return {
            "original_filename": img_path.name,
            "attacked_filename": output_filename,
            "target_class": target_class,
        }

    async def _record_patch_attack(
        self,
        db: AsyncSession,
        attack_dataset_name: str,
        model_version_id: UUID,
        base_dataset_id: UUID,
        patch_id: UUID,
        target_class: str,
        patch_scale: float,
        description: Optional[str],
        processed_count: int,
        attack_results: List[Dict[str, Any]],
        attack_dir: Path,
    ):
        from app.schemas.dataset_2d import AttackDataset2DCreate
        from app.models.dataset_2d import AttackType

        attack_data = AttackDataset2DCreate(
            name=attack_dataset_name,
            description=description,
            attack_type=AttackType.PATCH,
            target_class=target_class,
            target_model_version_id=model_version_id,
            base_dataset_id=base_dataset_id,
            patch_id=patch_id,
            parameters={
                "patch_scale": patch_scale,
                "storage_path": str(attack_dir),
                "processed_images": processed_count,
                "attack_results": attack_results,
            },
        )
        return await crud.attack_dataset_2d.create(db, obj_in=attack_data)

    def _write_attack_metadata(
        self,
        attack_dataset_db: Any,
        attack_dataset_name: str,
        model_version_id: UUID,
        base_dataset_id: UUID,
        patch_id: UUID,
        target_class: str,
        patch_scale: float,
        processed_count: int,
        attack_results: List[Dict[str, Any]],
        attack_dir: Path,
    ) -> None:
        metadata_file = attack_dir / "attack_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "attack_dataset_id": str(attack_dataset_db.id),
                    "attack_dataset_name": attack_dataset_name,
                    "model_version_id": str(model_version_id),
                    "base_dataset_id": str(base_dataset_id),
                    "patch_id": str(patch_id),
                    "target_class": target_class,
                    "patch_scale": patch_scale,
                    "processed_images": processed_count,
                    "created_at": datetime.now().isoformat(),
                    "results": attack_results,
                },
                f,
                indent=2,
            )

    def prepare_attack_dataset_archive(self, attack: Any) -> Path:
        storage_path = attack.parameters.get("storage_path")
        if not storage_path:
            raise ValueError("Attack dataset storage path not found")
        return self._dataset_exporter.create_archive(storage_path, attack.name)

    def cleanup_attack_dataset_archive(self, archive_path: Path) -> None:
        self._dataset_exporter.cleanup_archive(archive_path)


# Global instance
adversarial_patch_service = AdversarialPatchService()
