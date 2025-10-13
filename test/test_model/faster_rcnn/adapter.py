"""
Faster R-CNN Adapter for object detection.
This adapter integrates torchvision Faster R-CNN models with the backend system.
"""
import numpy as np
import torch
import torchvision
from torchvision.models.detection import fasterrcnn_resnet50_fpn
from torchvision.transforms import functional as F
from typing import Any, Tuple, List
from pathlib import Path

from app.ai.base_detector import BaseObjectDetector, Detection, BoundingBox, DetectionResult


class FasterRCNNDetector(BaseObjectDetector):
    """Adapter for torchvision Faster R-CNN models."""

    def load_model(self, weights_path: str = None, **kwargs) -> None:
        """
        Load Faster R-CNN model from weights file or use pretrained.

        Args:
            weights_path: Path to model weights. If None, uses local weights. Use 'pretrained' for COCO weights.
            **kwargs: Additional arguments
        """
        # Set device
        self.device = kwargs.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')

        # Default to local weights file
        if weights_path is None:
            weights_path = str(Path(__file__).parent / "fasterrcnn_resnet50_fpn_coco.pth")

        # Load model
        if weights_path == 'pretrained' or not Path(weights_path).exists():
            # Load pretrained model on COCO
            self.model = fasterrcnn_resnet50_fpn(pretrained=True)
            print(f"✓ Loaded pretrained Faster R-CNN (COCO)")
        else:
            # Load custom weights
            self.model = fasterrcnn_resnet50_fpn(pretrained=False)
            checkpoint = torch.load(weights_path, map_location=self.device)
            self.model.load_state_dict(checkpoint)
            print(f"✓ Loaded Faster R-CNN from {weights_path}")

        self.model = self.model.to(self.device)
        self.model.eval()

        # Get input size from config (Faster R-CNN uses variable sizes)
        self.input_size = self.config.get('input_size', [800, 800])

        # Mark as loaded
        self.is_loaded = True

        print(f"  Classes: {len(self.class_names)}")
        print(f"  Input size: {self.input_size}")
        print(f"  Device: {self.device}")

    def preprocess(self, image: np.ndarray) -> Any:
        """
        Preprocess image for Faster R-CNN.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format

        Returns:
            Preprocessed tensor
        """
        # Convert BGR to RGB
        image_rgb = image[:, :, ::-1].copy()

        # Convert to tensor and normalize
        image_tensor = torch.from_numpy(image_rgb).permute(2, 0, 1).float()
        image_tensor = image_tensor / 255.0

        # Normalize with ImageNet stats
        mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
        image_tensor = (image_tensor - mean) / std

        # Move to device
        image_tensor = image_tensor.to(self.device)

        return image_tensor

    def predict(self, preprocessed_input: Any) -> Any:
        """
        Run Faster R-CNN inference.

        Args:
            preprocessed_input: Preprocessed tensor from preprocess()

        Returns:
            Model predictions
        """
        with torch.no_grad():
            predictions = self.model([preprocessed_input])

        return predictions[0]  # Return first prediction (single image)

    def postprocess(
        self,
        model_output: Any,
        original_shape: Tuple[int, int],
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.5
    ) -> DetectionResult:
        """
        Postprocess Faster R-CNN output to Detection objects.

        Args:
            model_output: Model predictions from predict()
            original_shape: Original image shape (height, width) - unused (boxes already scaled)
            conf_threshold: Confidence threshold for filtering
            iou_threshold: IOU threshold for NMS (Faster R-CNN applies NMS internally)

        Returns:
            DetectionResult with filtered detections
        """
        detections = []

        # Extract predictions
        boxes = model_output['boxes'].cpu().numpy()
        labels = model_output['labels'].cpu().numpy()
        scores = model_output['scores'].cpu().numpy()

        # Filter by confidence
        for box, label, score in zip(boxes, labels, scores):
            if score < conf_threshold:
                continue

            # Boxes are in [x_min, y_min, x_max, y_max] format
            x1, y1, x2, y2 = box

            # Get class name
            class_id = int(label)
            class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"

            # Create detection
            detection = Detection(
                bbox=BoundingBox(
                    x1=float(x1),
                    y1=float(y1),
                    x2=float(x2),
                    y2=float(y2)
                ),
                class_id=class_id,
                class_name=class_name,
                confidence=float(score)
            )
            detections.append(detection)

        # Note: Faster R-CNN already applies NMS internally
        return DetectionResult(detections=detections)
