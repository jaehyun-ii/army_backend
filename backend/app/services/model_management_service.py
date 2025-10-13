"""
Model management utilities (load/unload/query).
"""
from typing import Any, Dict, Optional

from app.ai.model_loader import model_loader


class ModelManagementService:
    """Handle model lifecycle interactions with the shared loader."""

    async def load_model(self, version_id: str) -> Dict[str, Any]:
        detector = model_loader.load_model(version_id)
        return detector.get_model_info()

    async def get_model_info(self, version_id: str) -> Optional[Dict[str, Any]]:
        if version_id in model_loader.loaded_models:
            return model_loader.loaded_models[version_id].get_model_info()
        return None

    async def unload_model(self, version_id: str) -> None:
        model_loader.unload_model(version_id)


model_management_service = ModelManagementService()
