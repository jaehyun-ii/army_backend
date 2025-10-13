"""
Global PGD 2D Patch Generation Plugin.
"""
from typing import List, Tuple, Any
from pathlib import Path
import numpy as np
import logging

from app.plugins.base import DBSession
from app.plugins.patch_2d_base import Patch2DGenerationPlugin, Patch2DConfig
from app.ai.adversarial_patch_generator import GlobalPGDPatchGenerator

logger = logging.getLogger(__name__)


class GlobalPGDPatch2D(Patch2DGenerationPlugin):
    """
    Global PGD-based 2D adversarial patch generation.

    This plugin uses Projected Gradient Descent (PGD) to generate
    adversarial patches that are optimized across multiple images.
    """

    name = "global_pgd_2d"
    version = "1.0.0"
    description = "Global PGD-based 2D patch generation for object detection attacks"

    async def generate_patch(
        self,
        model_path: Path,
        image_bbox_list: List[Tuple[Path, List[float]]],
        target_class_id: int,
        config: Patch2DConfig,
        **kwargs
    ) -> Tuple[np.ndarray, float]:
        """
        Generate adversarial patch using Global PGD.

        Args:
            model_path: Path to model weights
            image_bbox_list: List of (image_path, bbox) tuples
            target_class_id: Target class ID in model
            config: Patch generation configuration

        Returns:
            Tuple of (patch_array, final_score)
        """
        logger.info(f"Generating Global PGD patch with {len(image_bbox_list)} samples")

        # Create generator instance
        generator = GlobalPGDPatchGenerator(
            model_path=str(model_path),
            patch_size=config.patch_size,
            area_ratio=config.area_ratio,
            epsilon=config.epsilon,
            alpha=config.alpha,
            iterations=config.iterations,
            batch_size=config.batch_size,
            input_size=config.input_size
        )

        # Generate patch
        patch_np, best_score = generator.generate_global_patch(
            image_bbox_list=image_bbox_list,
            target_class_id=target_class_id
        )

        logger.info(f"Patch generation complete. Final score: {best_score:.4f}")

        return patch_np, float(best_score)

    async def optimize_patch(
        self,
        patch: np.ndarray,
        model: Any,
        images: List[np.ndarray],
        bboxes: List[List[float]],
        target_class_id: int,
        config: Patch2DConfig,
        **kwargs
    ) -> Tuple[np.ndarray, List[float]]:
        """
        Optimize patch using PGD.

        Note: This is handled internally by GlobalPGDPatchGenerator.
        This method is provided for interface compatibility.
        """
        # This would be called if we need to optimize an existing patch
        # For now, use generate_patch which handles optimization internally
        raise NotImplementedError(
            "Use generate_patch method for Global PGD. "
            "This method would be used for fine-tuning existing patches."
        )

    async def validate_config(self, config: Patch2DConfig) -> bool:
        """Validate configuration."""
        if config.epsilon <= 0 or config.epsilon > 1.0:
            raise ValueError("epsilon must be between 0 and 1.0")
        if config.alpha <= 0 or config.alpha > config.epsilon:
            raise ValueError("alpha must be between 0 and epsilon")
        if config.iterations < 1:
            raise ValueError("iterations must be >= 1")
        if config.patch_size < 10:
            raise ValueError("patch_size must be >= 10")
        return True

    async def execute(
        self,
        config: Patch2DConfig,
        db_session: DBSession,
        **kwargs
    ) -> Any:
        """
        Execute patch generation attack.

        This is a placeholder - actual execution happens via generate_patch method.
        """
        raise NotImplementedError(
            "Use generate_patch() method directly for patch generation. "
            "The execute() method is not used for patch generation workflows."
        )
