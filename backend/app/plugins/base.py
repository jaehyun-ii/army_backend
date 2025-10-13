"""
Base classes for adversarial attack plugins.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
from pathlib import Path
import numpy as np
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

DBSession = Union[AsyncSession, Session]


class AttackCategory(str, Enum):
    """Attack category enumeration."""
    PATCH = "patch"
    NOISE = "noise"
    PHYSICAL = "physical"
    DIGITAL = "digital"


class AttackConfig(BaseModel):
    """Base configuration for attack plugins."""

    # Basic info
    name: str = Field(..., description="Attack name")
    description: Optional[str] = Field(None, description="Attack description")

    # Dataset info
    base_dataset_id: str = Field(..., description="Base dataset ID")
    output_dataset_name: str = Field(..., description="Output dataset name")

    # Optional model info
    model_version_id: Optional[str] = Field(None, description="Model version ID (if needed)")

    # Common parameters
    targeted: bool = Field(False, description="Whether this is a targeted attack")
    target_class: Optional[str] = Field(None, description="Target class (for targeted attacks)")

    # Metadata
    created_by: Optional[str] = Field(None, description="Creator ID")

    class Config:
        extra = "allow"  # Allow extra parameters for specific attacks


class AttackResult(BaseModel):
    """Result from attack execution."""

    success: bool = Field(..., description="Whether attack succeeded")
    output_path: Path = Field(..., description="Path to output dataset")

    # Statistics
    processed_images: int = Field(0, description="Number of images processed")
    failed_images: int = Field(0, description="Number of failed images")

    # Attack-specific metrics
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Attack-specific metrics")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        arbitrary_types_allowed = True


class AttackPlugin(ABC):
    """
    Base class for all adversarial attack plugins.

    All attack methods should inherit from this class and implement
    the required methods.
    """

    # Plugin metadata
    name: str = "base_attack"
    version: str = "1.0.0"
    category: AttackCategory = AttackCategory.DIGITAL
    description: str = "Base attack plugin"

    # Requirements
    requires_model: bool = False
    requires_gradient: bool = False
    supports_targeted: bool = False

    # Parameter schema
    config_schema: Dict[str, Any] = {}

    def __init__(self):
        """Initialize the plugin."""
        self.device = self._get_device()

    def _get_device(self):
        """Get computation device (CPU or CUDA)."""
        import torch
        return torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    @abstractmethod
    async def validate_config(self, config: AttackConfig) -> bool:
        """
        Validate attack configuration.

        Args:
            config: Attack configuration

        Returns:
            True if valid, raises ValueError otherwise
        """
        pass

    @abstractmethod
    async def execute(
        self,
        config: AttackConfig,
        db_session: DBSession,
        **kwargs
    ) -> AttackResult:
        """
        Execute the attack.

        Args:
            config: Attack configuration
            db_session: Database session
            **kwargs: Additional arguments

        Returns:
            AttackResult with output path and metrics
        """
        pass

    async def preprocess_image(
        self,
        image: np.ndarray,
        **kwargs
    ) -> np.ndarray:
        """
        Preprocess image before attack (optional).

        Args:
            image: Input image (numpy array)
            **kwargs: Additional arguments

        Returns:
            Preprocessed image
        """
        return image

    async def postprocess_image(
        self,
        image: np.ndarray,
        **kwargs
    ) -> np.ndarray:
        """
        Postprocess image after attack (optional).

        Args:
            image: Attacked image (numpy array)
            **kwargs: Additional arguments

        Returns:
            Postprocessed image
        """
        return image

    def get_config_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema for configuration parameters.

        Returns:
            JSON schema dict
        """
        return self.config_schema

    def get_info(self) -> Dict[str, Any]:
        """
        Get plugin information.

        Returns:
            Plugin metadata
        """
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "description": self.description,
            "requires_model": self.requires_model,
            "requires_gradient": self.requires_gradient,
            "supports_targeted": self.supports_targeted,
            "config_schema": self.config_schema
        }


class GradientBasedAttackPlugin(AttackPlugin):
    """
    Base class for gradient-based attacks (FGSM, PGD, etc.).
    """

    requires_model = True
    requires_gradient = True
    supports_targeted = True

    @abstractmethod
    async def compute_gradient(
        self,
        model: Any,
        image: np.ndarray,
        target_class_id: Optional[int] = None,
        targeted: bool = False,
        **kwargs
    ) -> np.ndarray:
        """
        Compute gradient for the attack.

        Args:
            model: Detection model
            image: Input image
            target_class_id: Target class ID (for targeted attacks)
            targeted: Whether this is targeted attack
            **kwargs: Additional arguments

        Returns:
            Gradient as numpy array
        """
        pass


class NoiseBasedAttackPlugin(AttackPlugin):
    """
    Base class for noise-based attacks (Gaussian, Uniform, etc.).
    """

    requires_model = False
    requires_gradient = False
    supports_targeted = False
    category = AttackCategory.NOISE

    @abstractmethod
    async def generate_noise(
        self,
        image_shape: tuple,
        **kwargs
    ) -> np.ndarray:
        """
        Generate noise for the attack.

        Args:
            image_shape: Shape of the image
            **kwargs: Noise parameters

        Returns:
            Noise as numpy array
        """
        pass


class PhysicalAttackPlugin(AttackPlugin):
    """
    Base class for physical attacks (patches, stickers, etc.).
    """

    category = AttackCategory.PHYSICAL
    requires_model = True
    supports_targeted = True
