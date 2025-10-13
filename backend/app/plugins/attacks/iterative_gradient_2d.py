"""
Iterative Gradient Attack Plugin.

This plugin implements an iterative gradient-based attack that repeatedly
applies gradients to reduce object detection confidence.
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


class IterativeGradient2D(GradientBasedNoise2DPlugin):
    """
    Iterative Gradient Attack.

    This attack iteratively applies gradients to reduce detection confidence
    until objects are no longer detected or max iterations reached.
    """

    name = "iterative_gradient_2d"
    version = "1.2.0"  # Added NCC-based termination, dynamic step size, increased default iterations
    description = "Iterative gradient-based attack for 2D object detection"

    def __init__(self):
        super().__init__()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        # Initialize DetectionLoss if available
        if DetectionLoss is not None:
            self.detection_loss = DetectionLoss(device=self.device)
        else:
            self.detection_loss = None
            logger.warning("DetectionLoss not available, will use fallback proxy loss")

        logger.info(f"IterativeGradient2D v{self.version} initialized with comprehensive bbox extraction")

    config_schema = {
        "type": "object",
        "properties": {
            "max_iterations": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 10000},  # Increased from 1000 to 10000
            "step_size": {"type": "number", "minimum": 0.0, "default": 1.0},  # Reduced from 10000.0 to 1.0 (in [0-1] normalized range)
            "epsilon": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.03},  # Max perturbation (L-infinity constraint)
            "stop_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.1},
            "ncc_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.6},  # NCC similarity threshold
            "targeted": {"type": "boolean", "default": True},
            "target_class": {"type": "string"},
            "model_version_id": {"type": "string"},
        },
        "required": ["model_version_id"]
    }

    def _compute_ncc(self, image1: torch.Tensor, image2: torch.Tensor) -> float:
        """
        Compute Normalized Cross-Correlation between two images.

        Args:
            image1: First image tensor
            image2: Second image tensor

        Returns:
            NCC value (higher = more similar, range roughly [0, 1])
        """
        # Flatten images
        img1_flat = image1.flatten()
        img2_flat = image2.flatten()

        # Normalize
        img1_norm = (img1_flat - img1_flat.mean()) / (img1_flat.std() + 1e-8)
        img2_norm = (img2_flat - img2_flat.mean()) / (img2_flat.std() + 1e-8)

        # Compute correlation
        ncc = (img1_norm * img2_norm).mean()

        return ncc.item()

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
        Generate iterative gradient attack noise.

        Args:
            image: Input image (H, W, C) in [0, 255]
            config: Noise configuration
            model: Detection model (required)
            **kwargs: May contain 'target_class_id', 'bboxes'

        Returns:
            Adversarial noise that when added makes objects undetectable
        """
        if model is None:
            raise ValueError("Iterative gradient attack requires a model")

        bboxes = kwargs.get('bboxes', [])
        target_class_id = kwargs.get('target_class_id')

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

        max_iterations = getattr(config, 'max_iterations', 10000)  # Increased default to match attack_detector capabilities
        step_size = getattr(config, 'step_size', 1.0)  # Changed from 10000.0 to 1.0
        epsilon = getattr(config, 'epsilon', 0.03)  # Max perturbation in [0-1] range
        stop_threshold = getattr(config, 'stop_threshold', 0.1)
        ncc_threshold = getattr(config, 'ncc_threshold', 0.6)  # NCC similarity threshold

        # Track original step size for dynamic adjustment
        original_step_size = step_size

        logger.info(f"Starting iterative gradient attack: max_iter={max_iterations}, step={step_size}, epsilon={epsilon}, ncc_threshold={ncc_threshold}")

        # Convert resized image to tensor
        img_tensor = torch.from_numpy(resized_image.transpose(2, 0, 1)).float() / 255.0
        img_tensor = img_tensor.unsqueeze(0).to(self.device)

        # Store original image
        original_tensor = img_tensor.clone()

        # Initialize perturbation
        perturbation = torch.zeros_like(img_tensor)

        # Get initial detection count
        with torch.no_grad():
            # Properly detach and clone for inference
            inference_tensor = img_tensor.detach().clone().contiguous()
            initial_output = model(inference_tensor)
            initial_count = self._count_detections(initial_output, target_class_id)

        logger.info(f"Initial detections: {initial_count}")

        if initial_count == 0:
            logger.warning("No objects detected initially, returning zero noise")
            return np.zeros_like(image, dtype=np.float32)

        # Initialize attack image
        attack_image = img_tensor.clone()

        # Set model to training mode to enable gradients
        # Access the underlying PyTorch model directly
        actual_model = model
        if hasattr(model, 'model'):
            actual_model = model.model

        model_was_training = actual_model.training if hasattr(actual_model, 'training') else False
        if hasattr(actual_model, 'train'):
            actual_model.train()

        logger.info(f"Model type: {type(model)}, Actual model type: {type(actual_model)}, Training mode: {actual_model.training if hasattr(actual_model, 'training') else 'unknown'}")

        # Log header for iteration details
        logger.info("=" * 140)
        logger.info(f"{'Iteration':<15} {'Det':<6} {'Loss':<12} {'Gradient':<12} {'Mask':<8} {'Perturbation':<14} {'NCC':<8} {'NCC_skip':<10}")
        logger.info("=" * 140)

        # Iterative attack loop
        for iteration in range(max_iterations):
            # Enable gradients explicitly
            attack_image.requires_grad_(True)

            # Forward pass - use the actual PyTorch model with gradients enabled
            with torch.set_grad_enabled(True):
                try:
                    # Use the actual PyTorch model (not the wrapper)
                    raw_output = actual_model(attack_image)

                    # Debug: log output type and structure
                    if iteration == 0:
                        logger.info(f"Raw output type: {type(raw_output)}")
                        if isinstance(raw_output, (list, tuple)):
                            logger.info(f"Raw output length: {len(raw_output)}")
                            if len(raw_output) > 0:
                                logger.info(f"First element type: {type(raw_output[0])}, shape: {raw_output[0].shape if hasattr(raw_output[0], 'shape') else 'N/A'}, requires_grad: {raw_output[0].requires_grad if hasattr(raw_output[0], 'requires_grad') else 'N/A'}")
                        else:
                            logger.info(f"Raw output shape: {raw_output.shape if hasattr(raw_output, 'shape') else 'N/A'}, requires_grad: {raw_output.requires_grad if hasattr(raw_output, 'requires_grad') else 'N/A'}")

                    # Compute loss from raw output
                    loss = self._compute_raw_detection_loss(raw_output, target_bboxes_tensor, target_class_id)
                except Exception as e:
                    logger.error(f"Error in forward pass with actual_model: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    # If this fails, the model might not be compatible with gradient-based attacks
                    logger.error(f"Cannot compute gradients - model incompatible with adversarial attacks")
                    break

            # Check if loss has gradients
            if not loss.requires_grad:
                logger.error(f"Loss at iteration {iteration} does not require gradients, stopping attack")
                break

            # Backward pass
            if attack_image.grad is not None:
                attack_image.grad.zero_()

            loss.backward()

            # Check if gradients were computed
            if attack_image.grad is None:
                logger.error(f"No gradients computed at iteration {iteration}, stopping attack")
                break

            # Get gradient
            grad = attack_image.grad.data

            # Compute gradient statistics
            grad_magnitude = grad.abs().mean().item()
            grad_max = grad.abs().max().item()

            # Get CURRENT detections for dynamic masking (like original code)
            with torch.no_grad():
                current_detections = self._get_current_detections(model, attack_image, target_class_id)
                current_count = len(current_detections)

            # Create DYNAMIC mask based on current detections (not fixed annotations)
            # Additionally check NCC (similarity) for each detected object
            mask = torch.zeros_like(grad)
            ncc_excluded_count = 0

            if len(current_detections) > 0:
                h, w = resized_h, resized_w  # Use resized dimensions
                for detection in current_detections:
                    x1, y1, x2, y2 = detection
                    x1 = int(max(0, min(x1, w)))
                    x2 = int(max(0, min(x2, w)))
                    y1 = int(max(0, min(y1, h)))
                    y2 = int(max(0, min(y2, h)))

                    if x2 > x1 and y2 > y1:
                        # Check NCC (similarity) between current and original for this region
                        current_region = attack_image[:, :, y1:y2, x1:x2]
                        original_region = original_tensor[:, :, y1:y2, x1:x2]

                        ncc = self._compute_ncc(current_region, original_region)

                        # Only attack this region if it's still similar enough to original
                        if ncc >= ncc_threshold:
                            # Add to mask (overlapping detections accumulate)
                            mask[:, :, y1:y2, x1:x2] += 1.0
                        else:
                            # Region has changed too much, skip it
                            ncc_excluded_count += 1
                            logger.debug(f"Skipping region [{x1},{y1},{x2},{y2}] - NCC {ncc:.3f} < threshold {ncc_threshold:.3f}")

                # Binarize mask: anywhere with detection = 1
                mask = torch.where(mask > 0, 1.0, 0.0)
            else:
                # No more detections - attack entire image to ensure they don't reappear
                mask = torch.ones_like(grad)

            # Compute mask coverage
            mask_coverage = (mask.sum() / mask.numel()).item() * 100

            # Apply masked gradient step with epsilon constraint
            with torch.no_grad():
                attack_image = attack_image.detach()
                perturbation_before = (attack_image - original_tensor).abs().mean().item()

                # Dynamic step size adjustment: reduce if approaching epsilon limit
                perturbation_max = (attack_image - original_tensor).abs().max().item()
                perturbation_ratio = perturbation_max / epsilon if epsilon > 0 else 0
                if perturbation_ratio > 0.9:
                    # Approaching epsilon limit, reduce step size
                    step_size = original_step_size * 0.5
                    if iteration % 10 == 0:  # Log occasionally to avoid spam
                        logger.debug(f"Reducing step size to {step_size:.6f} (perturbation ratio: {perturbation_ratio:.3f})")
                elif perturbation_ratio < 0.5 and step_size < original_step_size:
                    # Far from limit, restore step size
                    step_size = original_step_size
                    if iteration % 10 == 0:
                        logger.debug(f"Restoring step size to {step_size:.6f} (perturbation ratio: {perturbation_ratio:.3f})")

                # Apply gradient step
                attack_image += step_size * grad.sign() * mask  # Use sign for consistent step size

                # Project perturbation to epsilon ball (L-infinity constraint)
                perturbation = attack_image - original_tensor
                perturbation = torch.clamp(perturbation, -epsilon, epsilon)
                attack_image = original_tensor + perturbation

                # Ensure valid pixel range
                attack_image = torch.clamp(attack_image, 0.0, 1.0)
                perturbation_after = (attack_image - original_tensor).abs().mean().item()

            # Compute overall NCC
            overall_ncc = self._compute_ncc(attack_image, original_tensor)

            # Log detailed progress for each iteration
            logger.info(
                f"[Iter {iteration + 1:4d}/{max_iterations}] "
                f"Det: {current_count:3d} | "
                f"Loss: {loss.item():8.4f} | "
                f"Grad: {grad_magnitude:.6f} | "
                f"Mask: {mask_coverage:5.1f}% | "
                f"Pert: {perturbation_after:.6f} | "
                f"NCC: {overall_ncc:.3f} | "
                f"NCC_skip: {ncc_excluded_count}"
            )

            # Stop if detection count drops below threshold
            if current_count <= stop_threshold * initial_count:
                logger.info("=" * 140)
                logger.info(f"✓ Attack succeeded at iteration {iteration + 1}: {current_count} detections (threshold: {stop_threshold * initial_count:.1f})")
                break

            # Stop if all detected regions exceed NCC distortion limit (like attack_detector)
            all_regions_distorted = (ncc_excluded_count == len(current_detections) and current_count > 0)
            if all_regions_distorted:
                logger.info("=" * 140)
                logger.info(f"✓ Attack succeeded at iteration {iteration + 1}: All {current_count} regions exceed NCC distortion limit (too different from original)")
                break

        # Log completion
        logger.info("=" * 140)

        # Restore model to original mode
        if not model_was_training and hasattr(actual_model, 'eval'):
            actual_model.eval()

        # Convert perturbation back to noise in [0, 255] scale
        # Detach to remove gradients before converting to numpy
        noise = (attack_image - original_tensor).squeeze(0).detach().cpu().numpy()
        noise = noise.transpose(1, 2, 0) * 255.0

        # Resize noise back to original image dimensions if needed
        if noise.shape[:2] != (orig_h, orig_w):
            noise = cv2.resize(noise, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
            logger.info(f"Resized noise back to original dimensions ({orig_w}, {orig_h})")

        logger.info(f"Iterative gradient attack completed: {iteration + 1} iterations")
        logger.info(f"Final noise magnitude: {np.abs(noise).mean():.2f}")

        return noise.astype(np.float32)

    def _get_current_detections(self, model: Any, img_tensor: torch.Tensor, target_class_id: Optional[int] = None) -> List[List[float]]:
        """
        Get current detection bboxes from model output.

        This is used for dynamic masking - we mask based on WHERE objects are detected,
        not based on fixed annotation bboxes.

        Args:
            model: YOLO model
            img_tensor: Current image tensor
            target_class_id: Filter by this class if specified

        Returns:
            List of bbox coordinates [[x1, y1, x2, y2], ...]
        """
        detections = []

        try:
            logger.debug(f"[v{self.version}] Getting current detections with target_class_id={target_class_id}")

            # CRITICAL FIX: Ensure model is in eval mode for inference
            # Training mode causes YOLO to output different tensor shapes that break NMS
            actual_model = model
            if hasattr(model, 'model'):
                actual_model = model.model

            was_training = actual_model.training if hasattr(actual_model, 'training') else False
            if hasattr(actual_model, 'eval'):
                actual_model.eval()

            try:
                with torch.no_grad():
                    # Properly detach and clone the tensor to remove all gradient tracking
                    # This is critical to avoid shape mismatch errors in YOLO's NMS
                    inference_tensor = img_tensor.detach().clone()

                    # Ensure tensor is contiguous in memory
                    inference_tensor = inference_tensor.contiguous()

                    # Use the wrapper model for inference (not the raw model)
                    # The wrapper returns properly formatted Results objects
                    results = model(inference_tensor)

                # Handle different YOLO output formats
                if hasattr(results, '__len__') and len(results) > 0:
                    result = results[0]
                    logger.debug(f"Result type: {type(result)}, has boxes: {hasattr(result, 'boxes')}")

                    if hasattr(result, 'boxes'):
                        boxes = result.boxes
                        logger.debug(f"Boxes type: {type(boxes)}, boxes is None: {boxes is None}, len: {len(boxes) if boxes is not None else 'N/A'}")

                        # Check if boxes is None or empty
                        if boxes is None or len(boxes) == 0:
                            logger.debug("No boxes in results")
                            return []

                        # Comprehensive debugging of boxes object
                        logger.debug(f"Boxes attributes: {dir(boxes)}")

                        # Try to get bbox data - try multiple approaches
                        coords = None
                        cls = None

                        # Approach 1: Use boxes.data which contains raw bbox data
                        if hasattr(boxes, 'data'):
                            try:
                                data_tensor = boxes.data
                                logger.debug(f"boxes.data shape: {data_tensor.shape}, dtype: {data_tensor.dtype}")

                                # boxes.data format is typically [x1, y1, x2, y2, conf, cls]
                                if data_tensor.ndim == 2 and data_tensor.shape[1] >= 6:
                                    coords = data_tensor[:, :4].detach().cpu().numpy()  # First 4 columns are xyxy
                                    cls = data_tensor[:, 5].detach().cpu().numpy()  # 6th column is class
                                    logger.debug(f"Extracted from boxes.data - coords shape: {coords.shape}, cls shape: {cls.shape}")
                                elif data_tensor.ndim == 2 and data_tensor.shape[1] == 4:
                                    # Only bbox coordinates, no conf or class
                                    coords = data_tensor.detach().cpu().numpy()
                                    logger.debug(f"Extracted bbox only from boxes.data - coords shape: {coords.shape}")
                            except Exception as e:
                                logger.debug(f"Could not extract from boxes.data: {e}")

                        # Approach 2: Try boxes.xyxy if approach 1 failed
                        if coords is None and hasattr(boxes, 'xyxy'):
                            try:
                                xyxy_tensor = boxes.xyxy
                                logger.debug(f"boxes.xyxy type: {type(xyxy_tensor)}, shape: {xyxy_tensor.shape if hasattr(xyxy_tensor, 'shape') else 'N/A'}")

                                # Check if it's a proper 2D tensor
                                if hasattr(xyxy_tensor, 'shape'):
                                    if xyxy_tensor.ndim == 2 and xyxy_tensor.shape[1] == 4:
                                        coords = xyxy_tensor.detach().cpu().numpy()
                                        logger.debug(f"Extracted from boxes.xyxy - coords shape: {coords.shape}")
                                    else:
                                        logger.warning(f"boxes.xyxy has unexpected shape: {xyxy_tensor.shape} (expected 2D with 4 columns)")
                            except Exception as e:
                                logger.debug(f"Could not extract from boxes.xyxy: {e}")

                        # If we couldn't get coords, return empty
                        if coords is None:
                            logger.warning("Could not extract bbox coordinates from boxes object")
                            return []

                        # Validate coords shape
                        if coords.ndim != 2 or coords.shape[1] != 4:
                            logger.warning(f"Invalid coords shape {coords.shape}, expected (N, 4)")
                            return []

                        # Get class labels if not already extracted
                        if cls is None and target_class_id is not None and hasattr(boxes, 'cls'):
                            try:
                                cls_tensor = boxes.cls
                                logger.debug(f"boxes.cls type: {type(cls_tensor)}, shape: {cls_tensor.shape if hasattr(cls_tensor, 'shape') else 'N/A'}")
                                cls = cls_tensor.detach().cpu().numpy()

                                # Ensure cls is 1D
                                if cls.ndim > 1:
                                    cls = cls.flatten()
                                logger.debug(f"Extracted cls - shape: {cls.shape}")
                            except Exception as e:
                                logger.warning(f"Could not extract class labels: {e}")

                        # Filter by class if specified
                        if target_class_id is not None and cls is not None:
                            try:
                                logger.debug(f"Filtering: coords shape {coords.shape}, cls shape {cls.shape}, target_class_id {target_class_id}")

                                # Validate shapes match
                                if len(cls) != len(coords):
                                    logger.warning(f"Cls length {len(cls)} doesn't match coords length {len(coords)}, skipping class filter")
                                else:
                                    # Create boolean mask
                                    mask = (cls == target_class_id)
                                    logger.debug(f"Mask shape: {mask.shape}, mask sum: {mask.sum()}")

                                    # Apply mask
                                    coords = coords[mask]
                                    logger.debug(f"Filtered to {len(coords)} detections for class {target_class_id}")
                            except Exception as e:
                                logger.warning(f"Error filtering by class: {e}, using all detections")
                                import traceback
                                logger.warning(f"Traceback: {traceback.format_exc()}")

                        # Convert to list
                        detections = coords.tolist()
                        logger.debug(f"Returning {len(detections)} detections")

            finally:
                # Restore model to original training state
                if was_training and hasattr(actual_model, 'train'):
                    actual_model.train()
                elif not was_training and hasattr(actual_model, 'eval'):
                    # Already in eval, keep it that way (though we set it to eval above)
                    pass

        except Exception as e:
            logger.warning(f"Error getting current detections: {e}")
            import traceback
            logger.warning(f"Traceback: {traceback.format_exc()}")

        return detections

    def _count_detections(self, output: Any, target_class_id: Optional[int] = None) -> int:
        """
        Count number of detections in model output.

        Args:
            output: Model output (YOLO Results object or list of Results)
            target_class_id: If specified, only count this class

        Returns:
            Number of detections
        """
        try:
            # Handle YOLO Results object format (Ultralytics)
            if hasattr(output, '__len__') and len(output) > 0:
                result = output[0]

                # Check if it's a Results object with boxes attribute
                if hasattr(result, 'boxes'):
                    boxes = result.boxes

                    # If no boxes detected
                    if boxes is None or len(boxes) == 0:
                        return 0

                    # Filter by target class if specified
                    if target_class_id is not None and hasattr(boxes, 'cls'):
                        cls = boxes.cls.cpu().numpy()
                        mask = cls == target_class_id
                        return int(mask.sum())

                    # Return total number of boxes
                    if hasattr(boxes, 'xyxy'):
                        return len(boxes.xyxy)
                    elif hasattr(boxes, 'data'):
                        return len(boxes.data)

            # Fallback: try old tensor-based format
            if hasattr(output, 'pred'):
                pred = output.pred[0] if isinstance(output.pred, list) else output.pred
            elif isinstance(output, list) and len(output) > 0:
                pred = output[0]
                if not hasattr(pred, 'boxes'):  # Not a Results object
                    if hasattr(pred, 'shape'):
                        return pred.shape[0]

            return 0

        except Exception as e:
            logger.warning(f"Error counting detections: {e}")
            return 0

    def _compute_raw_detection_loss(
        self,
        raw_output: Any,
        target_bboxes: Optional[torch.Tensor] = None,
        target_class_id: Optional[int] = None
    ) -> torch.Tensor:
        """
        Compute detection loss from raw YOLO model output (with gradients).

        Args:
            raw_output: Raw model output (tuple of prediction tensors)
            target_bboxes: Ground truth bboxes
            target_class_id: Target class to attack

        Returns:
            Loss tensor with gradients
        """
        try:
            # Raw YOLO output is typically a tuple/list of tensors from different scales
            # Format: (batch, num_predictions, 85) where 85 = [x, y, w, h, objectness, class_probs...]

            if isinstance(raw_output, (list, tuple)):
                # YOLO returns predictions from multiple scales
                if len(raw_output) > 0:
                    # Use only the first prediction tensor (or concatenate if same shape)
                    if len(raw_output) == 1:
                        pred = raw_output[0]
                    else:
                        # Try to concatenate if shapes match in dimension 1
                        try:
                            # Check if all have same last dimension size
                            if all(t.shape[-1] == raw_output[0].shape[-1] for t in raw_output):
                                pred = torch.cat(raw_output, dim=1)
                            else:
                                # Different formats, just use the first one (usually main detection head)
                                logger.debug(f"Multiple output tensors with different shapes, using first one")
                                pred = raw_output[0]
                        except:
                            # If concatenation fails, use first tensor
                            pred = raw_output[0]
                else:
                    raise ValueError("Empty raw output")
            else:
                pred = raw_output

            # Ensure we have a batch dimension
            if len(pred.shape) == 2:
                pred = pred.unsqueeze(0)

            # Check if the prediction format is transposed (C, H*W) instead of (H*W, C)
            # YOLO outputs can be (batch, num_classes+4, num_anchors) or (batch, num_anchors, num_classes+4)
            if pred.shape[1] < pred.shape[2]:
                # Likely transposed format: (batch, features, anchors)
                # Transpose to (batch, anchors, features)
                pred = pred.transpose(1, 2)
                logger.debug(f"Transposed prediction tensor to shape: {pred.shape}")

            # YOLOv8/v11 format is [x, y, w, h, class_probs...] (no objectness)
            # YOLOv5 format is [x, y, w, h, objectness, class_probs...]

            # Check which format we have
            if pred.shape[-1] >= 5:
                # Try to extract confidence scores
                # For YOLOv8: first 4 are bbox, rest are class scores
                # For YOLOv5: first 4 are bbox, 5th is objectness, rest are class scores

                # Check if 5th element looks like objectness (should be in [0,1])
                fifth_element = pred[..., 4]

                # YOLOv8 format: bbox + class scores directly
                if pred.shape[-1] == 84:  # 4 bbox + 80 classes (COCO)
                    class_probs = pred[..., 4:]
                    if target_class_id is not None and target_class_id < class_probs.shape[-1]:
                        confidence = class_probs[..., target_class_id]
                    else:
                        confidence = class_probs.max(dim=-1)[0]  # Max class probability
                else:
                    # Assume YOLOv5 format or use objectness as confidence
                    objectness = pred[..., 4]

                    if target_class_id is not None and pred.shape[-1] > 5:
                        class_probs = pred[..., 5:]
                        if target_class_id < class_probs.shape[-1]:
                            target_class_score = class_probs[..., target_class_id]
                            confidence = objectness * target_class_score
                        else:
                            confidence = objectness
                    else:
                        confidence = objectness

                # Return negative sum to minimize confidence (fool detector)
                loss = -confidence.sum()

                logger.debug(f"Raw detection loss computed: {loss.item():.4f}, requires_grad: {loss.requires_grad}")
                return loss
            else:
                raise ValueError(f"Unexpected raw output shape: {pred.shape}")

        except Exception as e:
            logger.error(f"Error computing raw detection loss: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Cannot continue without proper loss
            raise RuntimeError(f"Failed to compute loss from raw output: {e}")

    def _compute_detection_loss(
        self,
        output: Any,
        target_bboxes: Optional[torch.Tensor] = None,
        target_class_id: Optional[int] = None
    ) -> torch.Tensor:
        """
        Compute detection loss to maximize (fool the detector).

        Uses actual YOLO detection loss (confidence + IoU) instead of simple proxy.

        Args:
            output: Model output
            target_bboxes: Ground truth bboxes in xyxy format, shape (N, 4)
            target_class_id: Target class to attack

        Returns:
            Loss tensor with gradients
        """
        try:
            # Use actual YOLO detection loss if available
            if self.detection_loss is not None:
                target_class_ids = [target_class_id] if target_class_id is not None else None
                loss = self.detection_loss(output, target_bboxes, target_class_ids)

                # Ensure loss has gradients
                if loss.requires_grad:
                    return loss
                else:
                    logger.warning("DetectionLoss returned tensor without gradients, using fallback")
                    raise ValueError("Loss doesn't have gradients")
            else:
                # DetectionLoss not available, use fallback immediately
                raise ImportError("DetectionLoss not available")

        except Exception as e:
            logger.debug(f"Error computing detection loss: {e}, using fallback proxy")

            # Fallback: Use a gradient-enabled proxy loss
            # Extract confidences that have gradients by accessing raw predictions
            try:
                # Try to get raw predictions with gradients
                if hasattr(output, '__len__') and len(output) > 0:
                    result = output[0]

                    # Check if result has raw predictions with gradients
                    if hasattr(result, 'boxes') and hasattr(result.boxes, 'data'):
                        # boxes.data contains [x1, y1, x2, y2, conf, class]
                        boxes_data = result.boxes.data

                        # Check if it has gradients
                        if boxes_data.requires_grad:
                            # Extract confidence (5th column)
                            conf = boxes_data[:, 4]

                            # Filter by class if specified
                            if target_class_id is not None and boxes_data.shape[1] > 5:
                                cls = boxes_data[:, 5]
                                mask = cls == target_class_id
                                conf = conf[mask]

                            if len(conf) > 0:
                                # Return negative sum to minimize confidence
                                return -conf.sum()

                # If we can't get gradient-enabled predictions, we cannot proceed
                logger.error("Could not extract gradient-enabled predictions from model output")
                raise RuntimeError("Model output does not contain gradients - incompatible with gradient-based attacks")

            except Exception as fallback_error:
                logger.error(f"Fallback loss computation failed: {fallback_error}")
                raise

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
        loss = self._compute_detection_loss(output, target_bboxes_tensor, target_class_id)

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
        max_iterations = getattr(config, 'max_iterations', 10000)
        step_size = getattr(config, 'step_size', 1.0)

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
        """
        Execute iterative gradient attack.

        This is a placeholder - actual execution happens via generate_noise method.
        """
        raise NotImplementedError(
            "Use generate_noise() method directly for noise generation. "
            "The execute() method is not used for noise generation workflows."
        )
