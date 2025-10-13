"""
CRUD operations for model repository
"""
from typing import List, Optional, Dict, Any
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import hashlib
import os
from datetime import datetime

from app.models.model_repo import (
    ODModel,
    ODModelVersion,
    ODModelClass,
    ODModelArtifact,
    ODModelDeployment,
    ModelFramework,
    ModelStage,
    ArtifactType
)


class CRUDModel:
    """CRUD operations for models."""

    async def create_model(
        self,
        db: AsyncSession,
        *,
        name: str,
        task: str = "object-detection",
        owner_id: Optional[UUID] = None,
        description: Optional[str] = None
    ) -> ODModel:
        """Create a new model."""
        db_model = ODModel(
            name=name,
            task=task,
            owner_id=owner_id,
            description=description
        )
        db.add(db_model)
        await db.flush()
        await db.refresh(db_model)
        return db_model

    async def get_model(self, db: AsyncSession, model_id: UUID) -> Optional[ODModel]:
        """Get model by ID."""
        result = await db.execute(
            select(ODModel).where(
                and_(
                    ODModel.id == model_id,
                    ODModel.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_model_by_name(self, db: AsyncSession, name: str) -> Optional[ODModel]:
        """Get model by name."""
        result = await db.execute(
            select(ODModel).where(
                and_(
                    ODModel.name == name,
                    ODModel.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_models(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[ODModel]:
        """List all models."""
        result = await db.execute(
            select(ODModel)
            .where(ODModel.deleted_at.is_(None))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


class CRUDModelVersion:
    """CRUD operations for model versions."""

    async def create_version(
        self,
        db: AsyncSession,
        *,
        model_id: UUID,
        version: str,
        framework: ModelFramework,
        framework_version: Optional[str] = None,
        input_spec: Optional[Dict] = None,
        training_metadata: Optional[Dict] = None,
        labelmap: Optional[Dict] = None,
        inference_params: Optional[Dict] = None,
        stage: ModelStage = ModelStage.DRAFT,
        created_by: Optional[UUID] = None
    ) -> ODModelVersion:
        """Create a new model version."""
        # Build kwargs, excluding None values for JSONB fields to avoid check constraint violations
        kwargs = {
            "model_id": model_id,
            "version": version,
            "framework": framework,
            "stage": stage,
        }

        # Add optional fields only if they have values
        if framework_version is not None:
            kwargs["framework_version"] = framework_version
        if input_spec is not None:
            kwargs["input_spec"] = input_spec
        if training_metadata is not None:
            kwargs["training_metadata"] = training_metadata
        if labelmap is not None:
            kwargs["labelmap"] = labelmap
        if inference_params is not None:
            kwargs["inference_params"] = inference_params
        if created_by is not None:
            kwargs["created_by"] = created_by

        db_version = ODModelVersion(**kwargs)
        db.add(db_version)
        await db.flush()
        await db.refresh(db_version)
        return db_version

    async def get_version(
        self,
        db: AsyncSession,
        version_id: UUID
    ) -> Optional[ODModelVersion]:
        """Get model version by ID."""
        result = await db.execute(
            select(ODModelVersion).where(
                and_(
                    ODModelVersion.id == version_id,
                    ODModelVersion.deleted_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_model_versions(
        self,
        db: AsyncSession,
        model_id: UUID
    ) -> List[ODModelVersion]:
        """Get all versions of a model."""
        result = await db.execute(
            select(ODModelVersion).where(
                and_(
                    ODModelVersion.model_id == model_id,
                    ODModelVersion.deleted_at.is_(None)
                )
            )
        )
        return list(result.scalars().all())

    async def update_stage(
        self,
        db: AsyncSession,
        version_id: UUID,
        stage: ModelStage
    ) -> Optional[ODModelVersion]:
        """Update model version stage."""
        db_version = await self.get_version(db, version_id)
        if db_version:
            db_version.stage = stage
            if stage == ModelStage.PRODUCTION:
                db_version.published_at = datetime.utcnow()
            await db.flush()
            await db.refresh(db_version)
        return db_version


class CRUDModelClass:
    """CRUD operations for model classes."""

    async def create_class(
        self,
        db: AsyncSession,
        *,
        model_version_id: UUID,
        class_index: int,
        class_name: str,
        metadata: Optional[Dict] = None
    ) -> ODModelClass:
        """Create a model class."""
        db_class = ODModelClass(
            model_version_id=model_version_id,
            class_index=class_index,
            class_name=class_name,
            metadata_=metadata
        )
        db.add(db_class)
        await db.flush()
        await db.refresh(db_class)
        return db_class

    async def create_classes_bulk(
        self,
        db: AsyncSession,
        *,
        model_version_id: UUID,
        classes: List[str]
    ) -> List[ODModelClass]:
        """Create multiple classes at once."""
        db_classes = []
        for idx, class_name in enumerate(classes):
            db_class = ODModelClass(
                model_version_id=model_version_id,
                class_index=idx,
                class_name=class_name
            )
            db_classes.append(db_class)

        db.add_all(db_classes)
        await db.flush()
        for db_class in db_classes:
            await db.refresh(db_class)
        return db_classes


class CRUDModelArtifact:
    """CRUD operations for model artifacts."""

    async def get_by_version(
        self,
        db: AsyncSession,
        version_id: UUID
    ) -> List[ODModelArtifact]:
        """Get all artifacts for a model version."""
        result = await db.execute(
            select(ODModelArtifact).where(
                and_(
                    ODModelArtifact.model_version_id == version_id,
                    ODModelArtifact.deleted_at.is_(None)
                )
            )
        )
        return list(result.scalars().all())

    async def create_artifact(
        self,
        db: AsyncSession,
        *,
        model_version_id: UUID,
        artifact_type: ArtifactType,
        storage_key: str,
        file_name: str,
        file_path: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> ODModelArtifact:
        """Create a model artifact."""
        # Calculate file info if file_path provided
        size_bytes = None
        sha256 = None

        if file_path and os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)

            # Calculate SHA256
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            sha256 = sha256_hash.hexdigest()

        # Build kwargs, excluding None values for JSONB fields
        kwargs = {
            "model_version_id": model_version_id,
            "artifact_type": artifact_type,
            "storage_key": storage_key,
            "file_name": file_name,
        }

        if size_bytes is not None:
            kwargs["size_bytes"] = size_bytes
        if sha256 is not None:
            kwargs["sha256"] = sha256
        if content_type is not None:
            kwargs["content_type"] = content_type
        if metadata is not None:
            kwargs["metadata_"] = metadata

        db_artifact = ODModelArtifact(**kwargs)
        db.add(db_artifact)
        await db.flush()
        await db.refresh(db_artifact)
        return db_artifact


class CRUDModelDeployment:
    """CRUD operations for model deployments."""

    async def create_deployment(
        self,
        db: AsyncSession,
        *,
        model_version_id: UUID,
        endpoint_url: Optional[str] = None,
        runtime: Optional[Dict] = None,
        region: Optional[str] = None,
        is_active: bool = True
    ) -> ODModelDeployment:
        """Create a model deployment."""
        db_deployment = ODModelDeployment(
            model_version_id=model_version_id,
            endpoint_url=endpoint_url,
            runtime=runtime,
            region=region,
            is_active=is_active
        )
        db.add(db_deployment)
        await db.flush()
        await db.refresh(db_deployment)
        return db_deployment

    async def deactivate_deployment(
        self,
        db: AsyncSession,
        deployment_id: UUID
    ) -> Optional[ODModelDeployment]:
        """Deactivate a deployment."""
        result = await db.execute(
            select(ODModelDeployment).where(
                ODModelDeployment.id == deployment_id
            )
        )
        db_deployment = result.scalar_one_or_none()

        if db_deployment:
            db_deployment.is_active = False
            await db.flush()
            await db.refresh(db_deployment)

        return db_deployment


# Create instances
crud_model = CRUDModel()
crud_model_version = CRUDModelVersion()
crud_model_class = CRUDModelClass()
crud_model_artifact = CRUDModelArtifact()
crud_model_deployment = CRUDModelDeployment()
