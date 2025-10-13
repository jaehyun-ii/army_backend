"""
Gaussian Noise 2D Attack Plugin.
"""
from typing import Optional, Any
import numpy as np
import logging

from app.plugins.base import DBSession
from app.plugins.noise_2d_base import RandomNoise2DPlugin, Noise2DConfig

logger = logging.getLogger(__name__)


class GaussianNoise2D(RandomNoise2DPlugin):
    """
    Gaussian noise attack.

    Adds Gaussian (normal) distributed noise to images.
    """

    name = "gaussian_2d"
    version = "1.0.0"
    description = "Gaussian noise attack for 2D images"

    config_schema = {
        "type": "object",
        "properties": {
            "mean": {"type": "number", "default": 0.0},
            "std": {"type": "number", "minimum": 0.0, "maximum": 255.0, "default": 25.0},
        },
        "required": ["std"]
    }

    async def generate_noise(
        self,
        image: np.ndarray,
        config: Noise2DConfig,
        model: Optional[Any] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Generate Gaussian noise.

        Args:
            image: Input image (H, W, C)
            config: Noise configuration with mean and std
            model: Not used for Gaussian noise

        Returns:
            Gaussian noise
        """
        mean = config.mean if config.mean is not None else 0.0
        std = config.std if config.std is not None else 25.0

        logger.info(f"Generating Gaussian noise with mean={mean}, std={std}")

        # Generate Gaussian noise
        noise = np.random.normal(mean, std, size=image.shape).astype(np.float32)

        logger.info(f"Generated noise with magnitude: {np.abs(noise).mean():.2f}")

        return noise

    async def validate_config(self, config: Noise2DConfig) -> bool:
        """Validate Gaussian noise config."""
        if config.std is None or config.std < 0:
            raise ValueError("std must be non-negative")

        return True

    async def execute(
        self,
        config: "Noise2DConfig",
        db_session: DBSession,
        **kwargs
    ) -> Any:
        """
        Execute Gaussian noise attack.

        This is a placeholder - actual execution happens via generate_noise method.
        """
        raise NotImplementedError(
            "Use generate_noise() method directly for noise generation. "
            "The execute() method is not used for noise generation workflows."
        )
