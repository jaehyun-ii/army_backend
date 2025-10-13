"""
Dynamic model loader for custom object detection models.

This module handles loading custom models with their adapters.
"""
from typing import Dict, Any, Optional
from pathlib import Path
import logging

from app.ai.base_detector import BaseObjectDetector
from app.ai.model_loader_components import (
    ModelAdapterLoader,
    ModelConfigLoader,
    ModelDependencyInstaller,
    ModelPathManager,
    ModelRegistry,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelLoader:
    """Handles dynamic loading of custom object detection models."""

    def __init__(self, models_base_path: Optional[str] = None):
        """
        Initialize model loader.

        Args:
            models_base_path: Base path where models are stored
        """
        self.paths = ModelPathManager(models_base_path)
        self.config_loader = ModelConfigLoader()
        self.dependency_installer = ModelDependencyInstaller()
        self.adapter_loader = ModelAdapterLoader()
        self.registry = ModelRegistry()

    def get_model_path(self, model_id: str) -> str:
        """
        Get path for a specific model.

        Args:
            model_id: Model ID

        Returns:
            Path to model directory
        """
        return str(self.paths.get_model_path(model_id))

    def load_config(self, model_path: str, strict: bool = False) -> Dict[str, Any]:
        """
        Load model configuration from config.yaml.

        Args:
            model_path: Path to model directory
            strict: If True, enforce recommended fields

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config.yaml not found
            ValueError: If config is invalid
        """
        config_file = Path(model_path) / "config.yaml"
        return self.config_loader.load(config_file, strict=strict)

    def install_requirements(self, model_path: str) -> bool:
        """
        Install dependencies from requirements.txt if present.

        Args:
            model_path: Path to model directory

        Returns:
            True if successful or no requirements, False otherwise
        """
        requirements_path = Path(model_path) / "requirements.txt"
        return self.dependency_installer.install_from(requirements_path)

    def load_adapter(self, model_path: str, validate: bool = True) -> type:
        """
        Dynamically load the adapter module.

        Args:
            model_path: Path to model directory
            validate: If True, perform security validation

        Returns:
            Detector class from adapter

        Raises:
            FileNotFoundError: If adapter.py not found
            ValueError: If adapter doesn't contain valid detector class or fails validation
        """
        return self.adapter_loader.load_adapter(Path(model_path) / "adapter.py", validate=validate)

    def load_model(
        self,
        model_id: str,
        install_deps: bool = True,
        force_reload: bool = False
    ) -> BaseObjectDetector:
        """
        Load a custom model.

        Args:
            model_id: Model ID
            install_deps: Whether to install requirements.txt
            force_reload: Force reload even if already loaded

        Returns:
            Loaded detector instance

        Raises:
            FileNotFoundError: If model files not found
            ValueError: If model configuration is invalid
        """
        # Return cached if already loaded
        if self.registry.is_loaded(model_id) and not force_reload:
            logger.info("Returning cached model %s", model_id)
            cached = self.registry.get(model_id)
            if cached is not None:
                return cached

        model_path = self.paths.get_model_path(model_id)
        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_path}")

        config = self.load_config(str(model_path))

        if install_deps:
            if not self.install_requirements(str(model_path)):
                raise RuntimeError(f"Failed to install requirements for {model_id}")

        detector_class = self.load_adapter(str(model_path))
        detector = detector_class(config)

        weights_path = self._find_weights_file(model_path, config)
        if not weights_path:
            raise FileNotFoundError(f"Weights file not found in {model_path}")

        # Load model weights
        logger.info("Loading model weights from %s", weights_path)
        detector.load_model(str(weights_path), **config.get("load_params", {}))

        # Set class names if provided in config
        if "class_names" in config:
            detector.set_class_names(config["class_names"])

        self.registry.register(model_id, detector)
        logger.info("Model %s loaded successfully", model_id)

        return detector

    def _find_weights_file(self, model_path: Path, config: Dict[str, Any]) -> Optional[Path]:
        """
        Find the weights file in model directory.

        Args:
            model_path: Path to model directory
            config: Model configuration

        Returns:
            Path to weights file or None
        """
        # Check if specified in config
        if "weights_file" in config:
            candidate = model_path / config["weights_file"]
            if candidate.exists():
                return candidate

        for file in model_path.iterdir():
            if file.suffix.lower() in settings.MODEL_WEIGHT_EXTENSIONS:
                return file

        return None

    def unload_model(self, model_id: str) -> None:
        """
        Unload a model from cache.

        Args:
            model_id: Model ID
        """
        if self.registry.is_loaded(model_id):
            self.registry.unload(model_id)
            logger.info("Model %s unloaded", model_id)

    def get_loaded_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about loaded models.

        Returns:
            Dictionary of loaded models and their info
        """
        return {
            model_id: detector.get_model_info()
            for model_id, detector in self.registry.loaded_models.items()
        }

    @property
    def loaded_models(self) -> Dict[str, BaseObjectDetector]:
        return self.registry.loaded_models


# Global model loader instance
model_loader = ModelLoader()
