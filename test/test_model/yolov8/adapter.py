"""
YOLOv8 Adapter for Ultralytics YOLO models.
This adapter integrates Ultralytics YOLO (v8/v11) with the backend system.
"""
import numpy as np
from typing import Any, Tuple
from pathlib import Path

from app.ai.base_detector import BaseObjectDetector, Detection, BoundingBox, DetectionResult


class YOLOv8Detector(BaseObjectDetector):
    """Adapter for Ultralytics YOLO (YOLOv8/v11) models."""

    def load_model(self, weights_path: str, **kwargs) -> None:
        """
        Load YOLOv8/v11 model from weights file.

        Args:
            weights_path: Path to .pt weights file
            **kwargs: Additional arguments (unused for YOLO)
        """
        from ultralytics import YOLO

        # Load model
        self.model = YOLO(weights_path)

        # Get input size from config (YOLO uses 640x640 by default)
        self.input_size = self.config.get('input_size', [640, 640])

        # Mark as loaded
        self.is_loaded = True

        print(f"✓ Loaded YOLOv8 model from {weights_path}")
        print(f"  Classes: {len(self.class_names)}")
        print(f"  Input size: {self.input_size}")

    def preprocess(self, image: np.ndarray) -> Any:
        """
        Preprocess image for YOLO.

        Ultralytics YOLO handles preprocessing internally,
        so we just pass the image as-is.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format

        Returns:
            Original image (YOLO handles preprocessing)
        """
        # YOLO's predict() handles preprocessing internally
        return image

    def predict(self, preprocessed_input: Any) -> Any:
        """
        Run YOLO inference.

        Args:
            preprocessed_input: Image from preprocess()

        Returns:
            YOLO Results object
        """
        # Run inference with YOLO
        # verbose=False to suppress output, imgsz for input size
        results = self.model.predict(
            preprocessed_input,
            imgsz=self.input_size[0],  # YOLO expects single int for square images
            verbose=False
        )
        return results[0]  # Return first result (single image)

    def postprocess(
        self,
        model_output: Any,
        original_shape: Tuple[int, int],
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45
    ) -> DetectionResult:
        """
        Postprocess YOLO output to Detection objects.

        Args:
            model_output: YOLO Results object from predict()
            original_shape: Original image shape (height, width) - unused (YOLO handles scaling)
            conf_threshold: Confidence threshold for filtering
            iou_threshold: IOU threshold for NMS

        Returns:
            DetectionResult with filtered detections
        """
        detections = []

        # YOLO Results object has boxes attribute
        boxes = model_output.boxes

        if boxes is None or len(boxes) == 0:
            return DetectionResult(detections=[])

        # Extract box data (already in xyxy format and scaled to original image)
        for box in boxes:
            # Get confidence
            conf = float(box.conf[0])

            # Filter by confidence
            if conf < conf_threshold:
                continue

            # Get class
            class_id = int(box.cls[0])
            class_name = self.class_names[class_id] if class_id < len(self.class_names) else f"class_{class_id}"

            # Get bounding box (already in xyxy format, scaled to original size)
            xyxy = box.xyxy[0].cpu().numpy()
            x1, y1, x2, y2 = xyxy

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
                confidence=conf
            )
            detections.append(detection)

        # Note: YOLO already applies NMS internally with default iou_threshold=0.45
        # If you need custom NMS, you can disable it in predict() and apply here

        return DetectionResult(detections=detections)
