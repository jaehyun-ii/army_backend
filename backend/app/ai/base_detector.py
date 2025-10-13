"""
Base interface for object detection models.

This module defines the standard interface that all custom object detection models
must implement to integrate with the system.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Bounding box representation."""
    x1: float = Field(..., description="Top-left x coordinate")
    y1: float = Field(..., description="Top-left y coordinate")
    x2: float = Field(..., description="Bottom-right x coordinate")
    y2: float = Field(..., description="Bottom-right y coordinate")

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}


class Detection(BaseModel):
    """Single detection result."""
    bbox: BoundingBox = Field(..., description="Bounding box")
    class_id: int = Field(..., description="Class ID")
    class_name: str = Field(..., description="Class name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bbox": self.bbox.to_dict(),
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": self.confidence
        }


class DetectionResult(BaseModel):
    """Detection results for an image."""
    detections: List[Detection] = Field(default_factory=list)
    inference_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "detections": [d.to_dict() for d in self.detections],
            "inference_time_ms": self.inference_time_ms,
            "metadata": self.metadata
        }


class BaseObjectDetector(ABC):
    """
    Base abstract class for object detection models.

    All custom models must inherit from this class and implement the required methods.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the detector.

        Args:
            config: Configuration dictionary loaded from config.yaml
        """
        self.config = config
        self.model = None
        self.class_names: List[str] = []
        self.is_loaded = False

    @abstractmethod
    def load_model(self, weights_path: str, **kwargs) -> None:
        """
        Load the model from weights file.

        Args:
            weights_path: Path to the model weights file
            **kwargs: Additional arguments from config
        """
        pass

    @abstractmethod
    def preprocess(self, image: np.ndarray) -> Any:
        """
        Preprocess the input image.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format

        Returns:
            Preprocessed image in model-specific format
        """
        pass

    @abstractmethod
    def predict(self, preprocessed_input: Any) -> Any:
        """
        Run inference on preprocessed input.

        Args:
            preprocessed_input: Preprocessed image from preprocess()

        Returns:
            Raw model output
        """
        pass

    @abstractmethod
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
        """
        pass

    def detect(
        self,
        image: np.ndarray,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45
    ) -> DetectionResult:
        """
        Perform end-to-end object detection.

        Args:
            image: Input image as numpy array (H, W, C) in BGR format
            conf_threshold: Confidence threshold
            iou_threshold: IOU threshold for NMS

        Returns:
            DetectionResult object
        """
        import time

        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        original_shape = image.shape[:2]
        start_time = time.time()

        # Run detection pipeline
        preprocessed = self.preprocess(image)
        output = self.predict(preprocessed)
        result = self.postprocess(output, original_shape, conf_threshold, iou_threshold)

        # Add inference time
        inference_time = (time.time() - start_time) * 1000
        result.inference_time_ms = inference_time

        return result

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model information.

        Returns:
            Dictionary with model metadata
        """
        return {
            "class_names": self.class_names,
            "num_classes": len(self.class_names),
            "is_loaded": self.is_loaded,
            "config": self.config
        }

    def set_class_names(self, class_names: List[str]) -> None:
        """
        Set class names for the model.

        Args:
            class_names: List of class names
        """
        self.class_names = class_names
