"""
Backward-compatible custom model service facade.

The legacy CustomModelService handled uploads, inference, management, and image
decoding. Those responsibilities now live in dedicated services; this module
adapts the new structure to the original API surface.
"""
from typing import Any, Dict, Optional, BinaryIO
import uuid

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.model_upload_service import (
    ModelUploadService,
    ModelUploadContext,
    model_upload_service,
)
from app.services.model_inference_service import (
    ModelInferenceService,
    model_inference_service,
)
from app.services.model_management_service import (
    ModelManagementService,
    model_management_service,
)


class CustomModelServiceFacade:
    """Facade providing the classic CustomModelService interface."""

    def __init__(
        self,
        upload_service: ModelUploadService,
        inference_service: ModelInferenceService,
        management_service: ModelManagementService,
    ):
        self._upload = upload_service
        self._inference = inference_service
        self._management = management_service

    async def upload_model(
        self,
        db: AsyncSession,
        model_name: str,
        version: str,
        framework: str,
        weights_file: BinaryIO,
        weights_filename: str,
        config_file: BinaryIO,
        adapter_file: BinaryIO,
        requirements_file: Optional[BinaryIO] = None,
        description: Optional[str] = None,
        owner_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        context = ModelUploadContext(
            model_name=model_name,
            version=version,
            framework=framework,
            weights_filename=weights_filename,
            description=description,
            owner_id=owner_id,
        )
        return await self._upload.upload_model(
            db=db,
            context=context,
            weights_file=weights_file,
            config_file=config_file,
            adapter_file=adapter_file,
            requirements_file=requirements_file,
        )

    async def load_model(self, version_id: str) -> Dict[str, Any]:
        return await self._management.load_model(version_id)

    async def run_inference(
        self,
        version_id: str,
        image: np.ndarray,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ):
        return await self._inference.run_inference(
            version_id=version_id,
            image=image,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
        )

    async def decode_image(self, image_base64: str) -> np.ndarray:
        return await self._inference.decode_image(image_base64)

    async def get_model_info(self, version_id: str) -> Optional[Dict[str, Any]]:
        return await self._management.get_model_info(version_id)

    async def unload_model(self, version_id: str) -> None:
        await self._management.unload_model(version_id)


custom_model_service = CustomModelServiceFacade(
    model_upload_service,
    model_inference_service,
    model_management_service,
)
