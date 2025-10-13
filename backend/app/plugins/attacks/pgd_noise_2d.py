"""
PGD 2D Noise Attack Plugin.
"""
from typing import Optional, Any, Tuple
import numpy as np
import torch
import cv2
import logging

from app.plugins.base import DBSession
from app.plugins.noise_2d_base import GradientBasedNoise2DPlugin, Noise2DConfig

logger = logging.getLogger(__name__)


class PGDNoise2D(GradientBasedNoise2DPlugin):
    """
    Projected Gradient Descent (PGD) noise attack.

    PGD iteratively applies FGSM-like steps with projection
    to ensure the noise stays within epsilon ball.
    """

    name = "pgd_2d"
    version = "1.0.0"
    description = "Projected Gradient Descent for 2D images"

    def __init__(self):
        super().__init__()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    config_schema = {
        "type": "object",
        "properties": {
            "epsilon": {"type": "number", "minimum": 0.0, "maximum": 255.0, "default": 8.0},
            "alpha": {"type": "number", "minimum": 0.0, "maximum": 255.0, "default": 2.0},
            "iterations": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 10},
            "targeted": {"type": "boolean", "default": False},
            "target_class": {"type": "string"},
            "model_version_id": {"type": "string"},
        },
        "required": ["epsilon", "alpha", "iterations", "model_version_id"]
    }

    def _resize_to_stride(self, image: np.ndarray, stride: int = 32) -> Tuple[np.ndarray, Tuple[int, int]]:
        """
        Resize image to dimensions divisible by stride.

        Args:
            image: Input image (H, W, C)
            stride: Stride to align to (default 32 for YOLO)

        Returns:
            Tuple of (resized_image, original_shape)
        """
        h, w = image.shape[:2]

        # Calculate new dimensions divisible by stride
        new_h = ((h + stride - 1) // stride) * stride
        new_w = ((w + stride - 1) // stride) * stride

        # Resize if necessary
        if new_h != h or new_w != w:
            resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            logger.info(f"Resized image from ({w}, {h}) to ({new_w}, {new_h}) for stride {stride}")
            return resized, (h, w)

        return image, (h, w)

    async def generate_noise(
        self,
        image: np.ndarray,
        config: Noise2DConfig,
        model: Optional[Any] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Generate PGD adversarial noise.

        Args:
            image: Input image (H, W, C) in [0, 255]
            config: Noise configuration
            model: Detection model (required)
            **kwargs: May contain 'target_class_id'

        Returns:
            Adversarial noise
        """
        if model is None:
            raise ValueError("PGD requires a model")

        logger.info(
            f"Generating PGD noise with epsilon={config.epsilon}, "
            f"alpha={config.alpha}, iterations={config.iterations}"
        )

        # Initialize noise randomly within epsilon ball
        noise = np.random.uniform(
            -config.epsilon,
            config.epsilon,
            size=image.shape
        ).astype(np.float32)

        # Iterative gradient steps
        for i in range(config.iterations):
            # Compute gradient on perturbed image
            perturbed = np.clip(image + noise, config.clip_min, config.clip_max)

            gradient = await self.compute_gradient(
                model=model,
                image=perturbed,
                target_class_id=kwargs.get('target_class_id'),
                targeted=config.targeted
            )

            # Update noise
            noise = noise + config.alpha * np.sign(gradient)

            # Project back to epsilon ball
            noise = np.clip(noise, -config.epsilon, config.epsilon)

            if (i + 1) % 10 == 0:
                logger.debug(f"PGD iteration {i+1}/{config.iterations}, "
                           f"avg noise: {np.abs(noise).mean():.2f}")

        logger.info(f"Generated PGD noise with magnitude: {np.abs(noise).mean():.2f}")

        return noise

    async def compute_gradient(
        self,
        model: Any,
        image: np.ndarray,
        target_class_id: Optional[int] = None,
        targeted: bool = False,
        **kwargs
    ) -> np.ndarray:
        """
        Compute gradient for PGD attack (same as FGSM).

        Args:
            model: YOLO model
            image: Input image
            target_class_id: Target class (for targeted attack)
            targeted: Whether this is targeted

        Returns:
            Gradient w.r.t. input image
        """
        # Store original dimensions
        orig_h, orig_w = image.shape[:2]

        # Resize image to dimensions divisible by 32 for YOLO
        resized_image, (orig_h, orig_w) = self._resize_to_stride(image, stride=32)

        # Convert to tensor
        img_tensor = torch.from_numpy(resized_image.transpose(2, 0, 1)).float() / 255.0
        img_tensor = img_tensor.unsqueeze(0).to(self.device)
        img_tensor.requires_grad = True

        # Forward pass
        outputs = model(img_tensor)

        # Compute loss
        if targeted:
            loss = -self._compute_detection_loss(outputs, target_class_id)
        else:
            loss = self._compute_detection_loss(outputs, target_class_id)

        # Backward pass
        loss.backward()

        # Get gradient
        gradient = img_tensor.grad.data.cpu().numpy()[0]
        gradient = gradient.transpose(1, 2, 0) * 255.0

        # Resize gradient back to original dimensions if needed
        if gradient.shape[:2] != (orig_h, orig_w):
            gradient = cv2.resize(gradient, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

        return gradient

    def _compute_detection_loss(self, outputs: Any, target_class_id: Optional[int] = None) -> torch.Tensor:
        """Compute detection loss from model outputs."""
        if hasattr(outputs, 'pred'):
            pred = outputs.pred[0] if isinstance(outputs.pred, list) else outputs
            if len(pred) > 0:
                confidences = pred[:, 4]
                if target_class_id is not None:
                    class_mask = pred[:, 5:].argmax(dim=1) == target_class_id
                    confidences = confidences[class_mask]

                return confidences.sum() if len(confidences) > 0 else torch.tensor(0.0)

        return torch.tensor(0.0)

    async def validate_config(self, config: "Noise2DConfig") -> bool:
        """Validate configuration."""
        if config.epsilon is None or config.epsilon <= 0:
            raise ValueError("epsilon must be > 0 for PGD")
        if config.alpha is None or config.alpha <= 0:
            raise ValueError("alpha must be > 0 for PGD")
        if config.iterations is None or config.iterations < 1:
            raise ValueError("iterations must be >= 1 for PGD")
        return True

    async def execute(
        self,
        config: "Noise2DConfig",
        db_session: DBSession,
        **kwargs
    ) -> Any:
        """
        Execute PGD noise attack.

        This is a placeholder - actual execution happens via generate_noise method.
        """
        raise NotImplementedError(
            "Use generate_noise() method directly for noise generation. "
            "The execute() method is not used for noise generation workflows."
        )
