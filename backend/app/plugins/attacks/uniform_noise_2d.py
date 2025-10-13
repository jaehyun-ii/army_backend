"""
Uniform Noise 2D Attack Plugin.
"""
from typing import Optional, Any
import numpy as np
import logging

from app.plugins.base import DBSession
from app.plugins.noise_2d_base import RandomNoise2DPlugin, Noise2DConfig

logger = logging.getLogger(__name__)


class UniformNoise2D(RandomNoise2DPlugin):
    """
    Uniform noise attack.

    Adds uniformly distributed noise to images.
    """

    name = "uniform_2d"
    version = "1.0.0"
    description = "Uniform noise attack for 2D images"

    config_schema = {
        "type": "object",
        "properties": {
            "min_val": {"type": "number", "default": -25.0},
            "max_val": {"type": "number", "default": 25.0},
        },
        "required": ["min_val", "max_val"]
    }

    async def generate_noise(
        self,
        image: np.ndarray,
        config: Noise2DConfig,
        model: Optional[Any] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Generate uniform noise.

        Args:
            image: Input image (H, W, C)
            config: Noise configuration with min_val and max_val
            model: Not used for uniform noise

        Returns:
            Uniform noise
        """
        min_val = config.min_val if config.min_val is not None else -25.0
        max_val = config.max_val if config.max_val is not None else 25.0

        logger.info(f"Generating uniform noise in range [{min_val}, {max_val}]")

        # Generate uniform noise
        noise = np.random.uniform(min_val, max_val, size=image.shape).astype(np.float32)

        logger.info(f"Generated noise with magnitude: {np.abs(noise).mean():.2f}")

        return noise

    async def validate_config(self, config: Noise2DConfig) -> bool:
        """Validate uniform noise config."""
        if config.min_val is None or config.max_val is None:
            raise ValueError("min_val and max_val required")

        if config.min_val >= config.max_val:
            raise ValueError("min_val must be less than max_val")

        return True

    async def execute(
        self,
        config: "Noise2DConfig",
        db_session: DBSession,
        **kwargs
    ) -> Any:
        """
        Execute Uniform noise attack.

        This is a placeholder - actual execution happens via generate_noise method.
        """
        raise NotImplementedError(
            "Use generate_noise() method directly for noise generation. "
            "The execute() method is not used for noise generation workflows."
        )
