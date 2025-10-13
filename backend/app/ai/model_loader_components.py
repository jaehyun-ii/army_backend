"""Helper components for the dynamic model loader."""
from __future__ import annotations

import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Type

import yaml

from app.ai.base_detector import BaseObjectDetector
from app.ai.validators import (
    AdapterValidator,
    ConfigValidator,
    YAMLSafetyValidator,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelPathManager:
    """Resolve and manage on-disk model locations."""

    def __init__(self, base_path: Optional[str] = None) -> None:
        self.base_path = Path(base_path or settings.get_storage_path("custom_models"))
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_model_path(self, model_id: str) -> Path:
        return self.base_path / model_id


class ModelConfigLoader:
    """Load and validate model configuration files."""

    def load(self, config_path: Path, *, strict: bool = False) -> Dict[str, any]:
        if not config_path.exists():
            raise FileNotFoundError(f"config.yaml not found in {config_path.parent}")

        logger.info("Validating YAML safety for %s", config_path)
        yaml_errors = YAMLSafetyValidator.validate_yaml_file(str(config_path))
        if yaml_errors:
            raise ValueError(f"YAML safety check failed: {'; '.join(yaml_errors)}")

        with open(config_path, "r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)

        logger.info("Validating config structure for %s", config_path)
        config_errors = ConfigValidator.validate(config, strict=strict)
        if config_errors:
            raise ValueError(f"Config validation failed: {'; '.join(config_errors)}")

        logger.info("Config validated successfully: %s", config.get("model_name", "unknown"))
        return config


class ModelDependencyInstaller:
    """Install optional model dependencies from requirements.txt."""

    def install_from(self, requirements_path: Path) -> bool:
        if not requirements_path.exists():
            logger.info("No requirements.txt found for model at %s", requirements_path.parent)
            return True

        try:
            logger.info("Installing requirements from %s", requirements_path)
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)]
            )
            logger.info("Requirements installed successfully")
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("Failed to install requirements: %s", exc)
            return False


class ModelAdapterLoader:
    """Load adapter modules that provide detector implementations."""

    def load_adapter(self, adapter_path: Path, *, validate: bool = True) -> Type[BaseObjectDetector]:
        if not adapter_path.exists():
            raise FileNotFoundError(f"adapter.py not found in {adapter_path.parent}")

        if validate:
            logger.info("Validating adapter security for %s", adapter_path)
            with open(adapter_path, "r", encoding="utf-8") as handle:
                code = handle.read()
            adapter_errors = AdapterValidator.validate_code(code, filename=str(adapter_path))
            if adapter_errors:
                raise ValueError(f"Adapter validation failed: {'; '.join(adapter_errors)}")

        module_name = f"custom_model_adapter_{adapter_path.parent.name}"
        spec = importlib.util.spec_from_file_location(module_name, adapter_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Failed to load adapter from {adapter_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseObjectDetector)
                and attr is not BaseObjectDetector
            ):
                logger.info("Loaded detector class: %s", attr.__name__)
                return attr

        raise ValueError(
            f"No valid detector class found in {adapter_path}. Adapter must contain a class "
            "that inherits from BaseObjectDetector."
        )


class ModelRegistry:
    """Track loaded model instances in memory."""

    def __init__(self) -> None:
        self._models: Dict[str, BaseObjectDetector] = {}

    def is_loaded(self, model_id: str) -> bool:
        return model_id in self._models

    def get(self, model_id: str) -> Optional[BaseObjectDetector]:
        return self._models.get(model_id)

    def register(self, model_id: str, detector: BaseObjectDetector) -> None:
        self._models[model_id] = detector

    def unload(self, model_id: str) -> None:
        self._models.pop(model_id, None)

    @property
    def loaded_models(self) -> Dict[str, BaseObjectDetector]:
        return self._models

