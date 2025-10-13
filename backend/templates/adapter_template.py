"""
Example adapter template for custom object detection models.

This file serves as a template for creating custom model adapters.
Copy this file and implement the required methods for your model.

Requirements:
1. Inherit from BaseObjectDetector
2. Implement all abstract methods: load_model, preprocess, predict, postprocess
3. Upload this file as adapter.py along with config.yaml and model weights
"""
import numpy as np
import torch
from typing import Any, Tuple, List

from app.ai.base_detector import BaseObjectDetector, Detection, BoundingBox, DetectionResult


class CustomDetector(BaseObjectDetector):
    """
    Custom object detection model adapter.

    Replace this implementation with your model-specific code.
    """

    def load_model(self, weights_path: str, **kwargs) -> None:
        """
        Load the model from weights file.

        Args:
            weights_path: Path to the model weights file
            **kwargs: Additional arguments from config.yaml

        Example for PyTorch:
            self.model = torch.load(weights_path)
            self.model.eval()

        Example for ONNX:
            import onnxruntime
            self.model = onnxruntime.InferenceSession(weights_path)
        """
        # Example: PyTorch model loading
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = torch.load(weights_path, map_location=self.device)
        self.model.eval()

        # Get input size from config
        self.input_size = self.config.get('input_size', [640, 640])

        self.is_loaded = True

    def preprocess(self, image: np.ndarray) -> Any:
        """
        Preprocess the input image.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format

        Returns:
            Preprocessed image in model-specific format

        Example preprocessing steps:
        1. Resize to model input size
        2. Convert BGR to RGB
        3. Normalize pixel values
        4. Convert to tensor format
        """
        import cv2

        # Resize to model input size
        img_resized = cv2.resize(image, tuple(self.input_size))

        # Convert BGR to RGB
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)

        # Normalize to [0, 1]
        img_normalized = img_rgb.astype(np.float32) / 255.0

        # Convert to tensor (C, H, W)
        img_tensor = torch.from_numpy(img_normalized).permute(2, 0, 1)

        # Add batch dimension
        img_batch = img_tensor.unsqueeze(0).to(self.device)

        return img_batch

    def predict(self, preprocessed_input: Any) -> Any:
        """
        Run inference on preprocessed input.

        Args:
            preprocessed_input: Preprocessed image from preprocess()

        Returns:
            Raw model output

        Example:
            with torch.no_grad():
                output = self.model(preprocessed_input)
            return output
        """
        with torch.no_grad():
            output = self.model(preprocessed_input)
        return output

    def postprocess(
        self,
        model_output: Any,
        original_shape: Tuple[int, int],
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45
    ) -> DetectionResult:
        """
        Postprocess model output to detection results.

        Args:
            model_output: Raw model output from predict()
            original_shape: Original image shape (height, width)
            conf_threshold: Confidence threshold for filtering detections
            iou_threshold: IOU threshold for NMS

        Returns:
            DetectionResult object

        This method should:
        1. Parse the raw model output
        2. Apply confidence thresholding
        3. Apply NMS (Non-Maximum Suppression)
        4. Scale bounding boxes back to original image size
        5. Create Detection objects
        """
        detections = []

        # Example: Parse model output
        # Assumes output format: [batch, num_detections, (x1, y1, x2, y2, conf, class_id)]
        output = model_output[0].cpu().numpy()  # Remove batch dimension

        # Filter by confidence
        output = output[output[:, 4] > conf_threshold]

        # Apply NMS (implement your NMS or use library function)
        output = self._apply_nms(output, iou_threshold)

        # Scale coordinates to original image size
        h_orig, w_orig = original_shape
        h_input, w_input = self.input_size
        scale_h = h_orig / h_input
        scale_w = w_orig / w_input

        for det in output:
            x1, y1, x2, y2, conf, class_id = det[:6]

            # Scale to original size
            x1 = float(x1 * scale_w)
            y1 = float(y1 * scale_h)
            x2 = float(x2 * scale_w)
            y2 = float(y2 * scale_h)

            # Get class name
            class_idx = int(class_id)
            class_name = self.class_names[class_idx] if class_idx < len(self.class_names) else f"class_{class_idx}"

            # Create detection
            detection = Detection(
                bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                class_id=class_idx,
                class_name=class_name,
                confidence=float(conf)
            )
            detections.append(detection)

        return DetectionResult(detections=detections)

    def _apply_nms(self, detections: np.ndarray, iou_threshold: float) -> np.ndarray:
        """
        Apply Non-Maximum Suppression.

        Args:
            detections: Array of detections (N, 6+) with format [x1, y1, x2, y2, conf, class_id, ...]
            iou_threshold: IOU threshold

        Returns:
            Filtered detections after NMS
        """
        if len(detections) == 0:
            return detections

        # Simple NMS implementation
        # For production, consider using torchvision.ops.nms or cv2.dnn.NMSBoxes

        # Sort by confidence
        sorted_indices = np.argsort(detections[:, 4])[::-1]
        detections = detections[sorted_indices]

        keep = []
        while len(detections) > 0:
            # Keep detection with highest confidence
            keep.append(detections[0])

            if len(detections) == 1:
                break

            # Calculate IOU with remaining detections
            ious = self._calculate_iou(detections[0, :4], detections[1:, :4])

            # Keep detections with IOU below threshold
            detections = detections[1:][ious < iou_threshold]

        return np.array(keep) if keep else np.array([])

    def _calculate_iou(self, box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        """
        Calculate IOU between one box and multiple boxes.

        Args:
            box: Single box [x1, y1, x2, y2]
            boxes: Multiple boxes (N, 4) with format [x1, y1, x2, y2]

        Returns:
            IOU values (N,)
        """
        # Calculate intersection
        x1 = np.maximum(box[0], boxes[:, 0])
        y1 = np.maximum(box[1], boxes[:, 1])
        x2 = np.minimum(box[2], boxes[:, 2])
        y2 = np.minimum(box[3], boxes[:, 3])

        intersection = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)

        # Calculate union
        box_area = (box[2] - box[0]) * (box[3] - box[1])
        boxes_area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        union = box_area + boxes_area - intersection

        # Calculate IOU
        iou = intersection / (union + 1e-6)

        return iou
