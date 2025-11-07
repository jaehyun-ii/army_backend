"""
Model factory for loading object detection models from .pt files.

Automatically detects model type and wraps with appropriate estimator.
Supports custom class mappings for models trained with different class orders.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import torch

from app.ai.estimators.object_detection import (
    PyTorchYolo,
    PyTorchRTDETR,
    PyTorchFasterRCNN,
)
from app.ai.estimators.object_detection.class_mapper import (
    ClassMapper,
    detect_class_format,
    COCO_CLASSES,
)

logger = logging.getLogger(__name__)


class ModelTypeDetector:
    """Detect model type from .pt file or metadata."""

    @staticmethod
    def detect_from_filename(filename: str) -> str:
        """
        Detect model type from filename.

        Returns:
            'yolo', 'rtdetr', 'faster_rcnn', 'efficientdet', or 'unknown'
        """
        filename_lower = filename.lower()

        if any(x in filename_lower for x in ['yolo', 'yolov', 'yolo11', 'yolo10', 'yolo8']):
            return 'yolo'
        elif 'rtdetr' in filename_lower or 'rt-detr' in filename_lower:
            return 'rtdetr'
        elif 'faster' in filename_lower and 'rcnn' in filename_lower:
            return 'faster_rcnn'
        elif 'efficient' in filename_lower and 'det' in filename_lower:
            return 'efficientdet'

        return 'unknown'

    @staticmethod
    def detect_from_state_dict(model_path: str) -> str:
        """
        Detect model type by inspecting state dict keys.

        Returns:
            Model type string
        """
        try:
            state_dict = torch.load(model_path, map_location='cpu')

            # Get model keys
            if isinstance(state_dict, dict):
                if 'model' in state_dict:
                    keys = state_dict['model'].state_dict().keys() if hasattr(state_dict['model'], 'state_dict') else []
                else:
                    keys = list(state_dict.keys())
            else:
                keys = []

            keys_str = ' '.join(str(k) for k in keys)

            # YOLO detection
            if any(x in keys_str for x in ['Detect', 'C2f', 'SPPF', 'Conv']):
                return 'yolo'

            # RT-DETR detection
            if any(x in keys_str for x in ['transformer', 'encoder', 'decoder']):
                return 'rtdetr'

            # Faster R-CNN detection
            if any(x in keys_str for x in ['rpn', 'roi_heads', 'backbone']):
                return 'faster_rcnn'

        except Exception as e:
            logger.warning(f"Failed to detect model type from state dict: {e}")

        return 'unknown'


class ModelFactory:
    """Factory for creating estimators from .pt files."""

    def __init__(self):
        self.detector = ModelTypeDetector()

    def load_model(
        self,
        model_path: str,
        model_type: Optional[str] = None,
        class_names: Optional[List[str]] = None,
        input_size: Optional[List[int]] = None,
        device_type: str = "auto",
        clip_values: tuple = (0, 255),
    ):
        """
        Load model from .pt file and wrap with appropriate estimator.

        Args:
            model_path: Path to .pt file
            model_type: Model type ('yolo', 'rtdetr', 'faster_rcnn', 'efficientdet')
                       If None, auto-detect from filename
            class_names: List of class names (optional)
            input_size: [height, width] (optional, default [640, 640])
            device_type: 'gpu', 'cpu', or 'auto'
            clip_values: Image value range (default (0, 255))

        Returns:
            Configured estimator instance
        """
        model_path_obj = Path(model_path)

        # Auto-detect model type if not provided
        if model_type is None:
            model_type = self.detector.detect_from_filename(model_path_obj.name)
            if model_type == 'unknown':
                model_type = self.detector.detect_from_state_dict(model_path)
            logger.info(f"Auto-detected model type: {model_type}")

        # Set defaults
        input_size = input_size or [640, 640]
        class_names = class_names or ["object"]  # Default single class

        # Build config
        config = {
            "class_names": class_names,
            "input_size": input_size,
        }

        # Load based on model type
        if model_type == 'yolo':
            return self._load_yolo(model_path, config, device_type, clip_values)
        elif model_type == 'rtdetr':
            return self._load_rtdetr(model_path, config, device_type, clip_values)
        elif model_type == 'faster_rcnn':
            return self._load_faster_rcnn(model_path, config, device_type, clip_values)
        elif model_type == 'efficientdet':
            return self._load_efficientdet(model_path, config, device_type, clip_values)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    def _load_yolo(self, model_path: str, config: dict, device_type: str, clip_values: tuple):
        """Load YOLO model using ultralytics."""
        try:
            from ultralytics import YOLO
        except ImportError:
            raise ImportError("ultralytics is required for YOLO models. Install with: pip install ultralytics")

        # Load ultralytics model
        yolo_model = YOLO(model_path)

        # Determine model name from path
        filename = Path(model_path).stem.lower()
        if 'yolo11' in filename or 'yolov11' in filename:
            model_name = 'yolov11'
        elif 'yolo10' in filename or 'yolov10' in filename:
            model_name = 'yolov10'
        elif 'yolo9' in filename or 'yolov9' in filename:
            model_name = 'yolov9'
        elif 'yolo8' in filename or 'yolov8' in filename:
            model_name = 'yolov8'
        else:
            model_name = 'yolov8'  # Default

        logger.info(f"Loading YOLO model: {model_name}")

        # Create estimator
        # channels_first=True (default) because ART expects NCHW input format
        # is_ultralytics=True will automatically wrap the model with PyTorchYoloLossWrapper
        # NOTE: Do NOT use preprocessing parameter - YOLO expects [0, 255] range
        # attack_losses must match what PyTorchYoloLossWrapper.forward() returns
        estimator = PyTorchYolo(
            model=yolo_model.model,
            input_shape=(3, *config['input_size']),
            channels_first=True,  # Input is NCHW (standard for PyTorch)
            device_type=device_type,
            clip_values=clip_values,
            attack_losses=("loss_total",),  # PyTorchYoloLossWrapper returns loss_total
            is_ultralytics=True,
            model_name=model_name,
        )

        logger.info(f"YOLO model loaded successfully: {model_name}")
        return estimator

    def _load_rtdetr(self, model_path: str, config: dict, device_type: str, clip_values: tuple):
        """Load RT-DETR model using ultralytics."""
        try:
            from ultralytics import RTDETR
        except ImportError:
            raise ImportError("ultralytics is required for RT-DETR models. Install with: pip install ultralytics")

        # Load RT-DETR model
        rtdetr_model = RTDETR(model_path)

        logger.info("Loading RT-DETR model")

        # Create estimator
        estimator = PyTorchRTDETR(
            model=rtdetr_model.model,
            input_shape=(3, *config['input_size']),
            device_type=device_type,
            clip_values=clip_values,
        )

        logger.info("RT-DETR model loaded successfully")
        return estimator

    def _load_faster_rcnn(self, model_path: str, config: dict, device_type: str, clip_values: tuple):
        """Load Faster R-CNN model."""
        # Load state dict
        state_dict = torch.load(model_path, map_location='cpu')

        # Create model architecture (this needs to be implemented based on your specific Faster R-CNN variant)
        # For now, we'll use torchvision's pre-trained model as base
        import torchvision

        model = torchvision.models.detection.fasterrcnn_resnet50_fpn(
            num_classes=len(config['class_names'])
        )

        # Load weights if compatible
        if isinstance(state_dict, dict) and 'model' in state_dict:
            model.load_state_dict(state_dict['model'])
        elif isinstance(state_dict, dict):
            model.load_state_dict(state_dict)

        logger.info("Loading Faster R-CNN model")

        # Create estimator
        estimator = PyTorchFasterRCNN(
            model=model,
            input_shape=(3, *config['input_size']),
            device_type=device_type,
            clip_values=clip_values,
        )

        logger.info("Faster R-CNN model loaded successfully")
        return estimator

    def _load_efficientdet(self, model_path: str, config: dict, device_type: str, clip_values: tuple):
        """Load EfficientDet model."""
        # EfficientDet support - would need effdet library
        # For now, treat as YOLO-like (many EfficientDet implementations use similar interface)
        try:
            from ultralytics import YOLO
            model = YOLO(model_path)

            estimator = PyTorchYolo(
                model=model.model,
                input_shape=(3, *config['input_size']),
                device_type=device_type,
                clip_values=clip_values,
                is_ultralytics=True,
                model_name='efficientdet',
            )

            logger.info("EfficientDet model loaded successfully")
            return estimator

        except Exception as e:
            logger.error(f"Failed to load EfficientDet model: {e}")
            raise ValueError(f"EfficientDet model loading not fully implemented. Error: {e}")


# Global factory instance
model_factory = ModelFactory()
