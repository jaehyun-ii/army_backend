"""
Model inference helpers.

SOLID Improvements:
- DIP: Depends on abstractions (model_loader, management_service)
- SRP: Single responsibility - inference execution and image decoding
"""
import base64
from typing import Optional

import cv2
import numpy as np

from app.ai.base_detector import DetectionResult
from app.ai.model_loader import model_loader, ModelLoader
from app.services.model_management_service import model_management_service, ModelManagementService


class ModelInferenceService:
    """
    Run inference and handle image decoding.

    This service focuses on inference execution. Model management
    is delegated to ModelManagementService for separation of concerns.
    """

    def __init__(
        self,
        *,
        management_service: Optional[ModelManagementService] = None,
        loader: Optional[ModelLoader] = None,
    ):
        """
        Initialize inference service with dependencies.

        Args:
            management_service: Service for model management (DI)
            loader: Model loader instance (DI)
        """
        self.management_service = management_service or model_management_service
        self.loader = loader or model_loader

    async def run_inference(
        self,
        version_id: str,
        image: np.ndarray,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ) -> DetectionResult:
        """
        Run object detection inference on an image.

        Args:
            version_id: Model version ID
            image: Input image as numpy array
            conf_threshold: Confidence threshold
            iou_threshold: IOU threshold for NMS

        Returns:
            Detection results
        """
        # Lazy load model if not loaded
        if version_id not in self.loader.loaded_models:
            await self.management_service.load_model(version_id)

        detector = self.loader.loaded_models[version_id]
        return detector.detect(image, conf_threshold, iou_threshold)

    async def decode_image(self, image_base64: str) -> np.ndarray:
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]

        image_bytes = base64.b64decode(image_base64)
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Failed to decode image")

        return image


model_inference_service = ModelInferenceService()

