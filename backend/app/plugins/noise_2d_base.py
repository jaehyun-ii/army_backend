"""
Base classes for 2D noise attack plugins.
"""
from abc import abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from pathlib import Path
import numpy as np

from .base import AttackPlugin, AttackCategory, AttackConfig, AttackResult


class Noise2DConfig(AttackConfig):
    """Configuration for 2D noise attacks."""

    # Noise type is determined by plugin

    # Common noise parameters
    epsilon: Optional[float] = Field(None, description="Noise strength/budget (0-255 scale)", ge=0.0, le=255.0)

    # For gradient-based noise (FGSM, PGD)
    model_version_id: Optional[str] = Field(None, description="Model version ID (for gradient-based)")
    alpha: Optional[float] = Field(None, description="Step size (for iterative methods, 0-255 scale)", ge=0.0, le=255.0)
    iterations: Optional[int] = Field(None, description="Number of iterations (for iterative)", ge=1, le=1000)

    # For random noise (Gaussian, Uniform)
    mean: Optional[float] = Field(None, description="Noise mean (for Gaussian)")
    std: Optional[float] = Field(None, description="Noise std (for Gaussian)")
    min_val: Optional[float] = Field(None, description="Min value (for Uniform)")
    max_val: Optional[float] = Field(None, description="Max value (for Uniform)")

    # Clipping
    clip_min: float = Field(0.0, description="Minimum pixel value after attack")
    clip_max: float = Field(255.0, description="Maximum pixel value after attack")


class Noise2DResult(AttackResult):
    """Result from 2D noise attack."""

    # Noise statistics
    avg_noise_magnitude: float = Field(0.0, description="Average noise magnitude")
    max_noise_magnitude: float = Field(0.0, description="Maximum noise magnitude")

    # Attack effectiveness (if model available)
    avg_confidence_drop: Optional[float] = Field(None, description="Average confidence drop")
    success_rate: Optional[float] = Field(None, description="Attack success rate")


class Noise2DAttackPlugin(AttackPlugin):
    """
    Base class for 2D noise attack plugins.

    This plugin adds adversarial noise to images to fool models.
    """

    category = AttackCategory.NOISE
    requires_model = False  # Some noise attacks don't need model
    requires_gradient = False
    supports_targeted = False

    @abstractmethod
    async def generate_noise(
        self,
        image: np.ndarray,
        config: Noise2DConfig,
        model: Optional[Any] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Generate adversarial noise for an image.

        Args:
            image: Input image (H, W, C)
            config: Noise configuration
            model: Optional model (for gradient-based attacks)
            **kwargs: Additional arguments

        Returns:
            Noise array same shape as image
        """
        pass

    async def apply_noise(
        self,
        image: np.ndarray,
        noise: np.ndarray,
        config: Noise2DConfig,
        bboxes: Optional[List[List[int]]] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Apply noise to image with clipping.
        If bboxes are provided, noise is only applied inside bounding boxes.

        Args:
            image: Original image
            noise: Noise to add
            config: Configuration with clipping bounds
            bboxes: Optional list of bounding boxes [[x1, y1, x2, y2], ...]
            **kwargs: Additional arguments

        Returns:
            Noisy image
        """
        noisy_image = image.copy().astype(np.float32)

        if bboxes and len(bboxes) > 0:
            # Apply noise only inside bounding boxes
            for bbox in bboxes:
                x1, y1, x2, y2 = map(int, bbox)
                # Ensure bbox is within image bounds
                h, w = image.shape[:2]
                x1 = max(0, min(x1, w))
                x2 = max(0, min(x2, w))
                y1 = max(0, min(y1, h))
                y2 = max(0, min(y2, h))

                if x2 > x1 and y2 > y1:
                    noisy_image[y1:y2, x1:x2] = image[y1:y2, x1:x2] + noise[y1:y2, x1:x2]
        else:
            # Apply noise to entire image (original behavior)
            noisy_image = image + noise

        noisy_image = np.clip(noisy_image, config.clip_min, config.clip_max)
        return noisy_image.astype(np.uint8)

    async def compute_noise_stats(
        self,
        noise: np.ndarray,
        **kwargs
    ) -> Dict[str, float]:
        """
        Compute statistics about the noise.

        Args:
            noise: Noise array
            **kwargs: Additional arguments

        Returns:
            Dictionary of noise statistics
        """
        return {
            "avg_magnitude": float(np.abs(noise).mean()),
            "max_magnitude": float(np.abs(noise).max()),
            "min_magnitude": float(np.abs(noise).min()),
            "std_magnitude": float(np.abs(noise).std()),
        }


class GradientBasedNoise2DPlugin(Noise2DAttackPlugin):
    """
    Base class for gradient-based 2D noise attacks (FGSM, PGD, etc.).
    """

    requires_model = True
    requires_gradient = True
    supports_targeted = True

    @abstractmethod
    async def compute_gradient(
        self,
        model: Any,
        image: np.ndarray,
        target_class_id: Optional[int] = None,
        targeted: bool = False,
        **kwargs
    ) -> np.ndarray:
        """
        Compute gradient for the attack.

        Args:
            model: Detection model
            image: Input image
            target_class_id: Target class ID (for targeted)
            targeted: Whether targeted attack
            **kwargs: Additional arguments

        Returns:
            Gradient array
        """
        pass

    async def validate_config(self, config: Noise2DConfig) -> bool:
        """Validate gradient-based noise config."""
        if not config.model_version_id:
            raise ValueError("model_version_id required for gradient-based attacks")

        if config.epsilon is None:
            raise ValueError("epsilon required for gradient-based attacks")

        if config.targeted and not config.target_class:
            raise ValueError("target_class required for targeted attack")

        return True


class RandomNoise2DPlugin(Noise2DAttackPlugin):
    """
    Base class for random 2D noise attacks (Gaussian, Uniform, etc.).
    """

    requires_model = False
    requires_gradient = False
    supports_targeted = False

    async def validate_config(self, config: Noise2DConfig) -> bool:
        """Validate random noise config."""
        # Each subclass may have different requirements
        return True
