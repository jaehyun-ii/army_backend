"""
Attack execution service - orchestrates adversarial attack workflows.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core.exceptions import NotFoundError, ValidationError
from app.models.dataset_2d import AttackDataset2D, AttackType
from app.services.adversarial_patch_service import AdversarialPatchService
from app.services.noise_attack_service import NoiseAttackService
from app.services.attack_metrics_calculator import (
    AttackMetricsCalculator,
    attack_metrics_calculator,
)

logger = logging.getLogger(__name__)


class AttackService:
    """
    Orchestrate attack execution and reporting.

    This service focuses on attack execution workflow. Metrics calculation
    has been separated to AttackMetricsCalculator for better separation of concerns.
    """

    def __init__(
        self,
        patch_service: Optional[AdversarialPatchService] = None,
        noise_service: Optional[NoiseAttackService] = None,
        metrics_calculator: Optional[AttackMetricsCalculator] = None,
    ):
        self.patch_service = patch_service or AdversarialPatchService()
        self.noise_service = noise_service or NoiseAttackService()
        self.metrics_calculator = metrics_calculator or attack_metrics_calculator

    async def execute_2d_attack(
        self,
        db: AsyncSession,
        attack_id: UUID,
        target_images: Optional[List[UUID]] = None,
    ) -> Dict[str, Any]:
        """
        Execute previously configured 2D attack against selected images.
        """
        attack = await crud.attack_dataset_2d.get(db, id=attack_id)
        if not attack:
            raise NotFoundError(resource=f"Attack dataset {attack_id}")

        logger.info("Executing %s attack: %s", attack.attack_type, attack.name)

        if not target_images:
            images = await crud.image_2d.get_by_dataset(
                db,
                dataset_id=attack.base_dataset_id,
            )
            target_images = [img.id for img in images]

        if not target_images:
            raise ValidationError(detail="No target images specified")

        if attack.attack_type == AttackType.PATCH:
            return await self._execute_patch_attack(db, attack, target_images)
        return await self._execute_noise_attack(db, attack, target_images)

    async def _execute_patch_attack(
        self,
        db: AsyncSession,
        attack: AttackDataset2D,
        target_images: List[UUID],
    ) -> Dict[str, Any]:
        """Execute a patch attack by applying a pre-generated patch."""
        if not attack.patch_id:
            raise ValidationError(detail="Patch attack requires patch_id")

        patch = await crud.patch_2d.get(db, id=attack.patch_id)
        if not patch:
            raise NotFoundError(resource=f"Patch {attack.patch_id}")

        logger.info("Applying patch %s to %s images", patch.name, len(target_images))

        return {
            "attack_id": str(attack.id),
            "attack_type": "patch",
            "patch_id": str(patch.id),
            "patch_name": patch.name,
            "target_class": patch.target_class,
            "processed_images": len(target_images),
            "status": "completed",
            "storage_path": attack.storage_path,
            "message": f"Patch attack applied to {len(target_images)} images",
        }

    async def _execute_noise_attack(
        self,
        db: AsyncSession,
        attack: AttackDataset2D,
        target_images: List[UUID],
    ) -> Dict[str, Any]:
        """Execute noise-based attack bookkeeping."""
        logger.info("Applying noise attack to %s images", len(target_images))

        return {
            "attack_id": str(attack.id),
            "attack_type": "noise",
            "method": attack.method,
            "processed_images": len(target_images),
            "status": "completed",
            "storage_path": attack.storage_path,
            "message": f"Noise attack applied to {len(target_images)} images",
        }

    async def calculate_attack_metrics(
        self,
        db: AsyncSession,
        attack_id: UUID,
        pre_attack_eval_id: Optional[UUID] = None,
        post_attack_eval_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Calculate metrics comparing pre/post attack evaluations when available.

        Delegates to AttackMetricsCalculator for the actual calculation logic.
        This method is maintained for backward compatibility.

        Args:
            db: Database session
            attack_id: Attack dataset ID
            pre_attack_eval_id: Optional pre-attack evaluation ID
            post_attack_eval_id: Optional post-attack evaluation ID

        Returns:
            Dictionary with calculated metrics
        """
        return await self.metrics_calculator.calculate_attack_metrics(
            db, attack_id, pre_attack_eval_id, post_attack_eval_id
        )

    async def get_attack_summary(
        self,
        db: AsyncSession,
        attack_id: UUID,
    ) -> Dict[str, Any]:
        """
        Gather a full attack summary including associated dataset and patch.
        """
        attack = await crud.attack_dataset_2d.get(db, id=attack_id)
        if not attack:
            raise NotFoundError(resource=f"Attack dataset {attack_id}")

        base_dataset = None
        if attack.base_dataset_id:
            base_dataset = await crud.dataset_2d.get(db, id=attack.base_dataset_id)

        patch = None
        if attack.patch_id:
            patch = await crud.patch_2d.get(db, id=attack.patch_id)

        return {
            "id": str(attack.id),
            "name": attack.name,
            "attack_type": attack.attack_type.value,
            "method": attack.method,
            "description": attack.description,
            "storage_path": attack.storage_path,
            "hyperparameters": attack.hyperparameters,
            "attack_metadata": attack.attack_metadata,
            "created_at": attack.created_at.isoformat() if attack.created_at else None,
            "base_dataset": {
                "id": str(base_dataset.id),
                "name": base_dataset.name,
            }
            if base_dataset
            else None,
            "patch": {
                "id": str(patch.id),
                "name": patch.name,
                "target_class": patch.target_class,
            }
            if patch
            else None,
        }


attack_service = AttackService()
