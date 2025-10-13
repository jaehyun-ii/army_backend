"""
Model upload service and helpers.
"""
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.model_repo import (
    ArtifactType,
    ModelFramework,
    ModelStage,
)
from app.crud.model_repo import (
    crud_model,
    crud_model_version,
    crud_model_artifact,
)

import logging
import yaml

logger = logging.getLogger(__name__)


@dataclass
class ModelUploadContext:
    """Context information required for uploading a model."""

    model_name: str
    version: str
    framework: str
    weights_filename: str
    description: Optional[str]
    owner_id: Optional[uuid.UUID]


@dataclass
class ArtifactFiles:
    """Container for stored artifact paths."""

    weights: Path
    config: Path
    adapter: Path
    requirements: Optional[Path] = None


class ModelFileHandler:
    """Handle filesystem operations for model uploads."""

    def create_temp_dir(self) -> Path:
        temp_dir = Path(settings.get_storage_path("temp_models"))
        temp_dir.mkdir(parents=True, exist_ok=True)
        upload_dir = temp_dir / f"model_upload_{uuid.uuid4().hex[:8]}"
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

    def save_uploads(
        self,
        temp_dir: Path,
        weights_file: BinaryIO,
        weights_filename: str,
        config_file: BinaryIO,
        adapter_file: BinaryIO,
        requirements_file: Optional[BinaryIO] = None,
    ) -> ArtifactFiles:
        safe_weights_name = Path(weights_filename).name
        weights_path = temp_dir / safe_weights_name
        with open(weights_path, "wb") as f:
            shutil.copyfileobj(weights_file, f)

        config_path = temp_dir / "config.yaml"
        with open(config_path, "wb") as f:
            shutil.copyfileobj(config_file, f)

        adapter_path = temp_dir / "adapter.py"
        with open(adapter_path, "wb") as f:
            shutil.copyfileobj(adapter_file, f)

        requirements_path = None
        if requirements_file:
            requirements_path = temp_dir / "requirements.txt"
            with open(requirements_path, "wb") as f:
                shutil.copyfileobj(requirements_file, f)

        return ArtifactFiles(
            weights=weights_path,
            config=config_path,
            adapter=adapter_path,
            requirements=requirements_path,
        )

    def move_to_storage(self, source_dir: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_dir), str(destination))

    def cleanup(self, temp_dir: Path) -> None:
        shutil.rmtree(temp_dir, ignore_errors=True)


class ModelConfigParser:
    """Parse uploaded configuration files for metadata."""

    def extract_labelmap(self, config_path: Path) -> Optional[Dict[str, str]]:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        if not config_data or "class_names" not in config_data:
            return None

        class_names = config_data["class_names"] or []
        if not class_names:
            return None

        labelmap = {str(i): name for i, name in enumerate(class_names)}
        logger.info(
            "Extracted labelmap with %s classes from %s",
            len(labelmap),
            config_path,
        )
        return labelmap


class ModelPersistenceManager:
    """Handle database operations for model uploads."""

    async def ensure_model(
        self,
        db: AsyncSession,
        model_name: str,
        description: Optional[str],
        owner_id: Optional[uuid.UUID],
    ):
        db_model = await crud_model.get_model_by_name(db, name=model_name)
        if not db_model:
            db_model = await crud_model.create_model(
                db,
                name=model_name,
                task="object-detection",
                owner_id=owner_id,
                description=description,
            )
        return db_model

    async def create_version(
        self,
        db: AsyncSession,
        model_id: uuid.UUID,
        version: str,
        framework: ModelFramework,
        labelmap: Optional[Dict[str, str]],
    ):
        return await crud_model_version.create_version(
            db,
            model_id=model_id,
            version=version,
            framework=framework,
            stage=ModelStage.DRAFT,
            labelmap=labelmap,
        )

    async def create_artifacts(
        self,
        db: AsyncSession,
        version_id: uuid.UUID,
        artifacts: ArtifactFiles,
        artifact_mapper,
    ) -> None:
        artifact_map = {
            "weights": artifacts.weights,
            "config": artifacts.config,
            "adapter": artifacts.adapter,
        }
        if artifacts.requirements:
            artifact_map["requirements"] = artifacts.requirements

        for artifact_type_str, path in artifact_map.items():
            await crud_model_artifact.create_artifact(
                db,
                model_version_id=version_id,
                artifact_type=artifact_mapper(artifact_type_str),
                storage_key=str(version_id),
                file_name=Path(path).name,
                file_path=str(path),
            )


class ModelUploadService:
    """Service responsible solely for uploading model artefacts."""

    def __init__(self):
        self.storage_root = Path(settings.STORAGE_ROOT) / "custom_models"
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self._file_handler = ModelFileHandler()
        self._config_parser = ModelConfigParser()
        self._persistence_manager = ModelPersistenceManager()

    async def upload_model(
        self,
        db: AsyncSession,
        *,
        context: ModelUploadContext,
        weights_file: BinaryIO,
        config_file: BinaryIO,
        adapter_file: BinaryIO,
        requirements_file: Optional[BinaryIO] = None,
    ) -> Dict[str, Any]:
        framework_enum = self._map_framework(context.framework)
        temp_dir = self._file_handler.create_temp_dir()

        try:
            artifact_files = self._file_handler.save_uploads(
                temp_dir=temp_dir,
                weights_file=weights_file,
                weights_filename=context.weights_filename,
                config_file=config_file,
                adapter_file=adapter_file,
                requirements_file=requirements_file,
            )

            labelmap = self._config_parser.extract_labelmap(artifact_files.config)

            db_model = await self._persistence_manager.ensure_model(
                db=db,
                model_name=context.model_name,
                description=context.description,
                owner_id=context.owner_id,
            )

            db_version = await self._persistence_manager.create_version(
                db=db,
                model_id=db_model.id,
                version=context.version,
                framework=framework_enum,
                labelmap=labelmap,
            )

            await self._persistence_manager.create_artifacts(
                db=db,
                version_id=db_version.id,
                artifacts=artifact_files,
                artifact_mapper=self._map_artifact_type,
            )

            final_path = self.storage_root / str(db_version.id)
            self._file_handler.move_to_storage(temp_dir, final_path)

            logger.info(
                "Custom model uploaded: %s v%s (ID: %s)",
                context.model_name,
                context.version,
                db_version.id,
            )

            return {
                "model_id": str(db_model.id),
                "version_id": str(db_version.id),
                "status": "success",
                "message": (
                    f"Model {context.model_name} version {context.version} uploaded successfully"
                ),
            }

        except Exception:
            self._file_handler.cleanup(temp_dir)
            logger.exception("Error uploading model")
            raise

    def _map_framework(self, framework: str) -> ModelFramework:
        framework_lower = framework.lower()
        mapping = {
            "pytorch": ModelFramework.PYTORCH,
            "tensorflow": ModelFramework.TENSORFLOW,
            "onnx": ModelFramework.ONNX,
            "tensorrt": ModelFramework.TENSORRT,
            "openvino": ModelFramework.OPENVINO,
        }
        return mapping.get(framework_lower, ModelFramework.CUSTOM)

    def _map_artifact_type(self, artifact_type: str) -> ArtifactType:
        mapping = {
            "weights": ArtifactType.WEIGHTS,
            "config": ArtifactType.CONFIG,
            "adapter": ArtifactType.SUPPORT,
            "requirements": ArtifactType.SUPPORT,
        }
        return mapping.get(artifact_type, ArtifactType.OTHER)


model_upload_service = ModelUploadService()
