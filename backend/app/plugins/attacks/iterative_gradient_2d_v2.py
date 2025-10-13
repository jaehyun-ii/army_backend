"""
Iterative Gradient Attack Plugin (Accurate Implementation).

This plugin implements the exact iterative gradient-based attack from test_iter_capture.py
that uses actual YOLO detection loss and dynamic bbox masking.
"""
from typing import Optional, Any, List, Tuple
import numpy as np
import torch
import cv2
import logging
from pathlib import Path

from app.plugins.noise_2d_base import GradientBasedNoise2DPlugin, Noise2DConfig

# Import DetectionLoss with try-except for robustness
try:
    from app.plugins.utils.yolo_loss import DetectionLoss
except ImportError:
    # Fallback: try relative import
    try:
        from ..utils.yolo_loss import DetectionLoss
    except ImportError:
        # If still fails, define a dummy class (will use fallback loss)
        import logging as _logging
        _logging.getLogger(__name__).warning("Could not import DetectionLoss, using fallback")
        DetectionLoss = None

logger = logging.getLogger(__name__)


class IterativeGradientV2_2D(GradientBasedNoise2DPlugin):
    """
    Iterative Gradient Attack (Accurate Implementation).

    This matches the original test_iter_capture.py implementation:
    - Uses actual YOLO detection loss (not just confidence sum)
    - Creates dynamic masks based on current detections (not fixed annotations)
    - Updates gradients every iteration
    """

    name = "iterative_gradient_v2_2d"
    version = "2.0.0"
    description = "Iterative gradient attack using YOLO detection loss (accurate)"

    def __init__(self):
        super().__init__()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        # Initialize DetectionLoss if available
        if DetectionLoss is not None:
            self.detection_loss = DetectionLoss(device=self.device)
        else:
            self.detection_loss = None
            logger.warning("DetectionLoss not available, will use fallback proxy loss")

    config_schema = {
        "type": "object",
        "properties": {
            "max_iterations": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 60000},
            "step_size": {"type": "number", "minimum": 0.0, "default": 10000.0},
            "stop_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.1},
            "targeted": {"type": "boolean", "default": True},
            "target_class": {"type": "string"},
            "model_version_id": {"type": "string"},
        },
        "required": ["model_version_id"]
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
        Generate iterative gradient attack noise using actual YOLO loss.

        This implementation matches test_iter_capture.py:
        1. Forward pass through YOLO model
        2. Compute actual detection loss (bbox + class + objectness)
        3. Backward pass to get gradients
        4. Create mask from CURRENT detections (not fixed annotations)
        5. Apply masked gradient step
        6. Repeat until detections drop below threshold

        Args:
            image: Input image (H, W, C) in [0, 255]
            config: Noise configuration
            model: YOLO model (required)
            **kwargs: May contain 'target_class_id'

        Returns:
            Adversarial noise
        """
        if model is None:
            raise ValueError("Iterative gradient attack requires a model")

        target_class_id = kwargs.get('target_class_id')
        bboxes = kwargs.get('bboxes', [])
        max_iterations = getattr(config, 'max_iterations', 60000)
        step_size = getattr(config, 'step_size', 10000.0)
        stop_threshold = getattr(config, 'stop_threshold', 0.1)

        # Store original image dimensions
        orig_h, orig_w = image.shape[:2]

        # Resize image to dimensions divisible by 32 for YOLO
        resized_image, (orig_h, orig_w) = self._resize_to_stride(image, stride=32)
        resized_h, resized_w = resized_image.shape[:2]

        # Scale bboxes if image was resized
        scaled_bboxes = []
        if bboxes and len(bboxes) > 0:
            scale_x = resized_w / orig_w
            scale_y = resized_h / orig_h
            for bbox in bboxes:
                x1, y1, x2, y2 = bbox
                scaled_bboxes.append([
                    x1 * scale_x,
                    y1 * scale_y,
                    x2 * scale_x,
                    y2 * scale_y
                ])

        # Convert scaled bboxes to tensor for loss computation
        target_bboxes_tensor = None
        if scaled_bboxes:
            target_bboxes_tensor = torch.tensor(scaled_bboxes, device=self.device, dtype=torch.float32)

        logger.info(f"Starting accurate iterative gradient attack: max_iter={max_iterations}, step={step_size}")

        # Convert resized image to tensor [B, C, H, W] in [0, 1] range
        img_tensor = torch.from_numpy(resized_image.transpose(2, 0, 1)).float() / 255.0
        img_tensor = img_tensor.unsqueeze(0).to(self.device)

        # Store original
        original_tensor = img_tensor.clone()

        # Get initial detection count using YOLO inference
        initial_count = self._get_detection_count(model, img_tensor, target_class_id)
        logger.info(f"Initial detections: {initial_count}")

        if initial_count == 0:
            logger.warning("No objects detected initially, returning zero noise")
            return np.zeros_like(image, dtype=np.float32)

        # Initialize attack image
        attack_image = img_tensor.clone()

        # Iterative attack loop
        for iteration in range(max_iterations):
            # Enable gradient
            attack_image.requires_grad_(True)

            # Forward pass through model
            output = model(attack_image)

            # Compute YOLO detection loss using actual loss function
            loss = self._compute_yolo_loss(output, target_bboxes_tensor, target_class_id)

            # Backward pass
            if attack_image.grad is not None:
                attack_image.grad.zero_()

            loss.backward()

            # Get gradient
            grad = attack_image.grad.data

            # Get current detections for dynamic masking
            with torch.no_grad():
                current_detections = self._get_current_detections(model, attack_image, target_class_id)
                current_count = len(current_detections)

            logger.debug(f"Iteration {iteration}: {current_count} detections")

            # Check stopping condition
            if current_count <= stop_threshold * initial_count:
                logger.info(f"Attack succeeded at iteration {iteration}: {current_count} detections")
                break

            # Create dynamic mask based on CURRENT detections (not fixed annotations)
            mask = torch.zeros_like(grad)
            if len(current_detections) > 0:
                h, w = resized_h, resized_w  # Use resized dimensions
                for detection in current_detections:
                    x1, y1, x2, y2 = detection
                    x1 = int(max(0, min(x1, w)))
                    x2 = int(max(0, min(x2, w)))
                    y1 = int(max(0, min(y1, h)))
                    y2 = int(max(0, min(y2, h)))

                    if x2 > x1 and y2 > y1:
                        # Add to mask (multiple detections can overlap)
                        mask[:, :, y1:y2, x1:x2] += 1.0

                # Binarize mask
                mask = torch.where(mask > 0, 1.0, 0.0)
            else:
                # No detections, attack entire image
                mask = torch.ones_like(grad)

            # Apply gradient step with mask
            with torch.no_grad():
                attack_image = attack_image.detach()
                attack_image += step_size * grad * mask
                attack_image = torch.clamp(attack_image, 0.0, 1.0)

        # Compute final noise
        noise = (attack_image - original_tensor).squeeze(0).cpu().numpy()
        noise = noise.transpose(1, 2, 0) * 255.0

        # Resize noise back to original image dimensions if needed
        if noise.shape[:2] != (orig_h, orig_w):
            noise = cv2.resize(noise, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
            logger.info(f"Resized noise back to original dimensions ({orig_w}, {orig_h})")

        logger.info(f"Iterative gradient attack completed: {iteration + 1} iterations")
        logger.info(f"Final noise magnitude: {np.abs(noise).mean():.2f}")

        return noise.astype(np.float32)

    def _get_detection_count(self, model: Any, img_tensor: torch.Tensor, target_class_id: Optional[int] = None) -> int:
        """Get number of detections."""
        with torch.no_grad():
            results = model(img_tensor)

        try:
            if hasattr(results, '__len__') and len(results) > 0:
                result = results[0]
                if hasattr(result, 'boxes'):
                    boxes = result.boxes
                    if target_class_id is not None and hasattr(boxes, 'cls'):
                        # Filter by class
                        mask = boxes.cls == target_class_id
                        return mask.sum().item()
                    return len(boxes)
        except:
            pass

        return 0

    def _get_current_detections(self, model: Any, img_tensor: torch.Tensor, target_class_id: Optional[int] = None) -> List[List[float]]:
        """Get current detection bboxes."""
        with torch.no_grad():
            results = model(img_tensor)

        detections = []
        try:
            if hasattr(results, '__len__') and len(results) > 0:
                result = results[0]
                if hasattr(result, 'boxes'):
                    boxes = result.boxes

                    # Get bbox coordinates
                    if hasattr(boxes, 'xyxy'):
                        coords = boxes.xyxy.cpu().numpy()

                        # Filter by class if specified
                        if target_class_id is not None and hasattr(boxes, 'cls'):
                            cls = boxes.cls.cpu().numpy()
                            mask = cls == target_class_id
                            coords = coords[mask]

                        detections = coords.tolist()
        except Exception as e:
            logger.warning(f"Error getting detections: {e}")

        return detections

    def _compute_yolo_loss(
        self,
        output: Any,
        target_bboxes: Optional[torch.Tensor] = None,
        target_class_id: Optional[int] = None
    ) -> torch.Tensor:
        """
        Compute YOLO detection loss using actual loss function.

        Uses DetectionLoss class which computes confidence + IoU loss.

        Args:
            output: YOLO model output
            target_bboxes: Ground truth bboxes in xyxy format
            target_class_id: Target class to attack

        Returns:
            Loss tensor
        """
        try:
            # Use actual YOLO detection loss if available
            if self.detection_loss is not None:
                target_class_ids = [target_class_id] if target_class_id is not None else None
                loss = self.detection_loss(output, target_bboxes, target_class_ids)
                return loss
            else:
                # DetectionLoss not available, use fallback immediately
                raise ImportError("DetectionLoss not available")

        except Exception as e:
            logger.warning(f"Error computing loss: {e}")
            # Fallback to confidence-based proxy loss
            try:
                if hasattr(output, '__len__') and len(output) > 0:
                    result = output[0]
                    if hasattr(result, 'boxes') and hasattr(result.boxes, 'conf'):
                        conf = result.boxes.conf
                        if target_class_id is not None and hasattr(result.boxes, 'cls'):
                            mask = result.boxes.cls == target_class_id
                            conf = conf[mask]
                        if len(conf) > 0:
                            return conf.sum()
            except:
                pass
            return torch.tensor(0.0, requires_grad=True, device=self.device)

    async def compute_gradient(
        self,
        model: Any,
        image: np.ndarray,
        target_class_id: Optional[int] = None,
        targeted: bool = False,
        **kwargs
    ) -> np.ndarray:
        """
        Compute gradient for iterative gradient attack.

        Note: This method is required by GradientBasedNoise2DPlugin abstract class,
        but iterative gradient attack computes gradients internally in generate_noise().

        This is a simplified single-step gradient computation for compatibility.

        Args:
            model: YOLO model
            image: Input image (H, W, C) in [0, 255]
            target_class_id: Target class ID
            targeted: Whether targeted attack
            **kwargs: Additional arguments (may contain 'bboxes')

        Returns:
            Gradient array (H, W, C)
        """
        # Store original dimensions
        orig_h, orig_w = image.shape[:2]

        # Resize image to dimensions divisible by 32 for YOLO
        resized_image, (orig_h, orig_w) = self._resize_to_stride(image, stride=32)
        resized_h, resized_w = resized_image.shape[:2]

        # Scale bboxes if provided
        bboxes = kwargs.get('bboxes', [])
        target_bboxes_tensor = None
        if bboxes and len(bboxes) > 0:
            scale_x = resized_w / orig_w
            scale_y = resized_h / orig_h
            scaled_bboxes = []
            for bbox in bboxes:
                x1, y1, x2, y2 = bbox
                scaled_bboxes.append([
                    x1 * scale_x,
                    y1 * scale_y,
                    x2 * scale_x,
                    y2 * scale_y
                ])
            target_bboxes_tensor = torch.tensor(scaled_bboxes, device=self.device, dtype=torch.float32)

        # Convert resized image to tensor
        img_tensor = torch.from_numpy(resized_image.transpose(2, 0, 1)).float() / 255.0
        img_tensor = img_tensor.unsqueeze(0).to(self.device)
        img_tensor.requires_grad_(True)

        # Forward pass
        output = model(img_tensor)

        # Compute loss
        loss = self._compute_yolo_loss(output, target_bboxes_tensor, target_class_id)

        # Backward pass
        if img_tensor.grad is not None:
            img_tensor.grad.zero_()
        loss.backward()

        # Get gradient
        grad = img_tensor.grad.data.squeeze(0).cpu().numpy()
        grad = grad.transpose(1, 2, 0) * 255.0  # Convert to [0, 255] scale

        # Resize gradient back to original dimensions if needed
        if grad.shape[:2] != (orig_h, orig_w):
            grad = cv2.resize(grad, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

        return grad.astype(np.float32)

    async def validate_config(self, config: "Noise2DConfig") -> bool:
        """Validate configuration."""
        max_iterations = getattr(config, 'max_iterations', 60000)
        step_size = getattr(config, 'step_size', 10000.0)

        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        if step_size < 0:
            raise ValueError("step_size must be >= 0")

        return True

    async def execute(
        self,
        config: "Noise2DConfig",
        db_session: Any,
        **kwargs
    ) -> Any:
        """Execute iterative gradient attack."""
        raise NotImplementedError(
            "Use generate_noise() method directly for noise generation."
        )
