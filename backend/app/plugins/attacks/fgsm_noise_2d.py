"""
FGSM 2D Noise Attack Plugin.
"""
from typing import Optional, Any, Tuple
import numpy as np
import torch
import cv2
import logging

from app.plugins.base import DBSession
from app.plugins.noise_2d_base import GradientBasedNoise2DPlugin, Noise2DConfig

logger = logging.getLogger(__name__)


class FGSMNoise2D(GradientBasedNoise2DPlugin):
    """
    Fast Gradient Sign Method (FGSM) noise attack.

    FGSM generates adversarial noise by taking a single step in the
    direction of the gradient sign.
    """

    name = "fgsm_2d"
    version = "1.0.0"
    description = "Fast Gradient Sign Method for 2D images"

    def __init__(self):
        super().__init__()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    config_schema = {
        "type": "object",
        "properties": {
            "epsilon": {"type": "number", "minimum": 0.0, "maximum": 255.0, "default": 8.0},
            "targeted": {"type": "boolean", "default": False},
            "target_class": {"type": "string"},
            "model_version_id": {"type": "string"},
        },
        "required": ["epsilon", "model_version_id"]
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
        Generate FGSM adversarial noise.

        Args:
            image: Input image (H, W, C) in [0, 255]
            config: Noise configuration
            model: Detection model (required)
            **kwargs: May contain 'target_class_id'

        Returns:
            Adversarial noise
        """
        if model is None:
            raise ValueError("FGSM requires a model")

        logger.info(f"Generating FGSM noise with epsilon={config.epsilon}")

        # Compute gradient
        gradient = await self.compute_gradient(
            model=model,
            image=image,
            target_class_id=kwargs.get('target_class_id'),
            targeted=config.targeted
        )

        # FGSM: noise = epsilon * sign(gradient)
        noise = config.epsilon * np.sign(gradient)

        logger.info(f"Generated noise with magnitude: {np.abs(noise).mean():.2f}")

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
        Compute gradient for FGSM attack.

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
            # For targeted attack, minimize loss for target class
            # (This is simplified - actual implementation depends on model output format)
            loss = -self._compute_detection_loss(outputs, target_class_id)
        else:
            # For untargeted, maximize overall loss
            loss = self._compute_detection_loss(outputs, target_class_id)

        # Backward pass
        loss.backward()

        # Get gradient
        gradient = img_tensor.grad.data.cpu().numpy()[0]
        gradient = gradient.transpose(1, 2, 0) * 255.0  # Back to [0, 255] scale

        # Resize gradient back to original dimensions if needed
        if gradient.shape[:2] != (orig_h, orig_w):
            gradient = cv2.resize(gradient, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

        return gradient

    def _compute_detection_loss(self, outputs: Any, target_class_id: Optional[int] = None) -> torch.Tensor:
        """
        Compute detection loss from model outputs.

        This is a simplified implementation. In practice, this should
        be tailored to the specific model's output format.
        """
        # Placeholder: actual implementation depends on YOLO output format
        # For now, return a simple confidence-based loss
        if hasattr(outputs, 'pred'):
            # YOLOv5/v8 format
            pred = outputs.pred[0] if isinstance(outputs.pred, list) else outputs
            if len(pred) > 0:
                confidences = pred[:, 4]  # Objectness scores
                if target_class_id is not None:
                    # Filter by class
                    class_mask = pred[:, 5:].argmax(dim=1) == target_class_id
                    confidences = confidences[class_mask]

                return confidences.sum() if len(confidences) > 0 else torch.tensor(0.0)

        return torch.tensor(0.0)

    async def validate_config(self, config: "Noise2DConfig") -> bool:
        """Validate configuration."""
        if config.epsilon is None or config.epsilon <= 0:
            raise ValueError("epsilon must be > 0 for FGSM")
        return True

    async def execute(
        self,
        config: "Noise2DConfig",
        db_session: DBSession,
        **kwargs
    ) -> Any:
        """
        Execute FGSM noise attack.

        This is a placeholder - actual execution happens via generate_noise method.
        """
        raise NotImplementedError(
            "Use generate_noise() method directly for noise generation. "
            "The execute() method is not used for noise generation workflows."
        )
