"""
Backward-compatible facade for attack-related services.

DEPRECATION NOTICE:
    This module serves as a facade for backward compatibility.
    The original module mixed multiple service classes, violating single responsibility.
    Each service now lives in a dedicated file:
    - AttackService → app.services.attack_execution_service
    - InferenceService → app.services.inference_service
    - DatasetStatisticsService → app.services.dataset_management_service

    This facade re-exports them for legacy imports from `app.services.attack_service`.

MIGRATION GUIDE:
    Old: from app.services.attack_service import AttackService
    New: from app.services.attack_execution_service import AttackService

    Old: from app.services.attack_service import InferenceService
    New: from app.services.inference_service import InferenceService

    Old: from app.services.attack_service import DatasetService
    New: from app.services.dataset_management_service import DatasetStatisticsService

Maintained for backward compatibility but may be removed in future versions.
"""
import warnings

from app import crud  # re-exported for legacy tests that patch this module
from app.services.attack_execution_service import AttackService, attack_service
from app.services.inference_service import InferenceService, inference_service
from app.services.dataset_management_service import (
    DatasetStatisticsService,
    dataset_statistics_service,
)

# Issue deprecation warning when this module is imported
warnings.warn(
    "Importing from 'app.services.attack_service' is deprecated. "
    "Please import directly from:\n"
    "  - app.services.attack_execution_service (for AttackService)\n"
    "  - app.services.inference_service (for InferenceService)\n"
    "  - app.services.dataset_management_service (for DatasetStatisticsService)\n"
    "This facade module may be removed in a future version.",
    DeprecationWarning,
    stacklevel=2,
)

# Retro-compatible aliases
DatasetService = DatasetStatisticsService
dataset_service = dataset_statistics_service

__all__ = [
    "AttackService",
    "attack_service",
    "InferenceService",
    "inference_service",
    "DatasetStatisticsService",
    "dataset_statistics_service",
    "DatasetService",
    "dataset_service",
]
