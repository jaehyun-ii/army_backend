"""
Backward compatibility shim for attack_service imports.

DEPRECATED: This module is deprecated. Please update your imports to use the new module structure.

This file re-exports everything from attack_service_facade for backward compatibility.
It allows existing code that imports from `app.services.attack_service` to continue working
while migration to the new structure is in progress.
"""
# Re-export everything from the facade
from app.services.attack_service_facade import *  # noqa: F401, F403

__all__ = [
    "AttackService",
    "attack_service",
    "InferenceService",
    "inference_service",
    "DatasetStatisticsService",
    "dataset_statistics_service",
    "DatasetService",
    "dataset_service",
    "crud",
]
