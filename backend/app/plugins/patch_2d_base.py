"""
Base classes for 2D adversarial patch generation plugins.
"""
from abc import abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field
from pathlib import Path
import numpy as np

from .base import AttackPlugin, AttackCategory, AttackConfig, AttackResult


class Patch2DConfig(AttackConfig):
    """Configuration for 2D patch generation."""

    # Patch parameters
    patch_size: int = Field(100, description="Base patch size in pixels", ge=10, le=1000)
    area_ratio: float = Field(0.3, description="Patch area ratio relative to bbox", ge=0.01, le=1.0)

    # Training parameters
    epsilon: float = Field(0.6, description="Perturbation budget", ge=0.0, le=1.0)
    alpha: float = Field(0.03, description="Learning rate", ge=0.0, le=1.0)
    iterations: int = Field(100, description="Number of training iterations", ge=1, le=10000)
    batch_size: int = Field(8, description="Batch size for training", ge=1, le=128)

    # Model and target
    model_version_id: str = Field(..., description="Model version ID to attack")
    target_class: str = Field(..., description="Target class name")

    # Optional
    input_size: int = Field(640, description="Model input size", ge=32, le=2048)


class Patch2DResult(AttackResult):
    """Result from 2D patch generation."""

    patch_path: Path = Field(..., description="Path to generated patch file")
    patch_size: Tuple[int, int] = Field(..., description="Final patch size (H, W)")

    # Training metrics
    initial_score: float = Field(0.0, description="Initial attack score")
    final_score: float = Field(0.0, description="Final attack score after training")
    training_loss: List[float] = Field(default_factory=list, description="Loss per iteration")

    # Dataset info
    num_training_samples: int = Field(0, description="Number of training samples used")
    target_class_id: int = Field(..., description="Target class ID in model")


class Patch2DGenerationPlugin(AttackPlugin):
    """
    Base class for 2D adversarial patch generation plugins.

    This plugin generates adversarial patches that can be applied to images
    to fool object detection models.
    """

    category = AttackCategory.PATCH
    requires_model = True
    requires_gradient = True
    supports_targeted = True

    config_schema = {
        "type": "object",
        "properties": {
            "patch_size": {"type": "integer", "minimum": 10, "maximum": 1000, "default": 100},
            "area_ratio": {"type": "number", "minimum": 0.01, "maximum": 1.0, "default": 0.3},
            "epsilon": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.6},
            "alpha": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.03},
            "iterations": {"type": "integer", "minimum": 1, "maximum": 10000, "default": 100},
            "batch_size": {"type": "integer", "minimum": 1, "maximum": 128, "default": 8},
            "target_class": {"type": "string"},
        },
        "required": ["target_class", "model_version_id", "base_dataset_id"]
    }

    @abstractmethod
    async def generate_patch(
        self,
        model_path: Path,
        image_bbox_list: List[Tuple[Path, List[float]]],
        target_class_id: int,
        config: Patch2DConfig,
        **kwargs
    ) -> Tuple[np.ndarray, float]:
        """
        Generate adversarial patch.

        Args:
            model_path: Path to model weights
            image_bbox_list: List of (image_path, bbox) tuples
            target_class_id: Target class ID in model
            config: Patch generation configuration
            **kwargs: Additional arguments

        Returns:
            Tuple of (patch_array, final_score)
        """
        pass

    @abstractmethod
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
        Optimize patch using gradient descent.

        Args:
            patch: Initial patch
            model: Detection model
            images: List of training images
            bboxes: List of bounding boxes
            target_class_id: Target class ID
            config: Configuration
            **kwargs: Additional arguments

        Returns:
            Tuple of (optimized_patch, loss_history)
        """
        pass

    async def initialize_patch(
        self,
        patch_size: int,
        method: str = "random",
        **kwargs
    ) -> np.ndarray:
        """
        Initialize patch with given method.

        Args:
            patch_size: Size of square patch
            method: Initialization method ('random', 'gray', 'noise')
            **kwargs: Additional arguments

        Returns:
            Initialized patch array (H, W, 3)
        """
        if method == "random":
            return np.random.rand(patch_size, patch_size, 3).astype(np.float32)
        elif method == "gray":
            return np.ones((patch_size, patch_size, 3), dtype=np.float32) * 0.5
        elif method == "noise":
            return np.random.normal(0.5, 0.1, (patch_size, patch_size, 3)).astype(np.float32)
        else:
            raise ValueError(f"Unknown initialization method: {method}")

    async def validate_config(self, config: Patch2DConfig) -> bool:
        """Validate patch generation configuration."""
        if config.targeted and not config.target_class:
            raise ValueError("target_class required for targeted attack")

        if config.patch_size < 10:
            raise ValueError("patch_size must be at least 10")

        if not 0.0 <= config.epsilon <= 1.0:
            raise ValueError("epsilon must be in [0, 1]")

        return True
