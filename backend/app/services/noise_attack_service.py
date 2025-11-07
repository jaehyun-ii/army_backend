"""
Noise attack service for creating FGSM/PGD attacked datasets.

This service implements single-step workflow:
    base_dataset → apply noise → attacked_dataset
"""
from __future__ import annotations

import logging
import numpy as np
import cv2
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.dataset_2d import AttackType
from app.services.sse_support import SSELogger, SSEManager
from app.services.estimator_loader_service import EstimatorLoaderService
from app.services.model_inference_service import model_inference_service

# ART imports - use real ART library for attacks
from art.attacks.evasion import FastGradientMethod, ProjectedGradientDescent
from art.estimators.object_detection import PyTorchYolo as ARTPyTorchYolo

logger = logging.getLogger(__name__)

# Shared SSE manager instance for all attack services
from app.services.patch_attack_service import _shared_sse_manager


class NoiseAttackService:
    """
    Service for creating noise-based attacked datasets (FGSM, PGD).

    Workflow:
        1. Load base_dataset images
        2. Load model as estimator
        3. Apply ART noise attack (FastGradientMethod or ProjectedGradientDescent)
        4. Save attacked images to new dataset
        5. Create AttackDataset2D record
    """

    def __init__(self):
        self.storage_root = Path(settings.STORAGE_ROOT)
        self.attack_datasets_dir = self.storage_root / "attack_datasets"
        self.attack_datasets_dir.mkdir(parents=True, exist_ok=True)

        self.estimator_loader = EstimatorLoaderService()
        # Use shared SSE manager
        self.sse_manager = _shared_sse_manager

    async def create_noise_attack_dataset(
        self,
        db: AsyncSession,
        attack_name: str,
        attack_method: str,
        base_dataset_id: UUID,
        model_id: UUID,
        epsilon: float,
        alpha: Optional[float] = None,
        iterations: Optional[int] = None,
        session_id: Optional[str] = None,
        current_user_id: Optional[UUID] = None,
    ) -> Tuple[schemas.AttackDataset2DResponse, UUID]:
        """
        Create noise-based attacked dataset.

        Args:
            db: Database session
            attack_name: Name for the attacked dataset
            attack_method: "fgsm" or "pgd"
            base_dataset_id: Source dataset to attack
            model_id: Target model for attack
            epsilon: Maximum perturbation (in [0, 255] scale)
            alpha: Step size for PGD (in [0, 255] scale, optional)
            iterations: Number of iterations for PGD (optional)
            session_id: SSE session ID for progress updates
            current_user_id: User ID for ownership

        Returns:
            Tuple of (AttackDataset2D response, output_dataset_id)
        """
        # Create SSE session if session_id provided and not already created
        if session_id and session_id not in self.sse_manager._event_queues:
            self.sse_manager.create_session(session_id)
            logger.info(f"Service: Created SSE session: {session_id}")
        elif session_id:
            logger.info(f"Service: SSE session already exists: {session_id}")

        # Initialize SSE logger
        sse_logger = SSELogger(logger, self.sse_manager, session_id)

        try:
            # Validate attack method
            if attack_method not in ["fgsm", "pgd"]:
                raise ValidationError(f"Invalid attack method: {attack_method}. Must be 'fgsm' or 'pgd'")

            # Validate PGD parameters
            if attack_method == "pgd":
                if alpha is None:
                    alpha = epsilon / 4  # Default: 1/4 of epsilon
                if iterations is None:
                    iterations = 10  # Default iterations

            await sse_logger.status("공격 데이터셋 생성 시작...")

            # Step 1: Load base dataset
            await sse_logger.status("베이스 데이터셋 로딩 중...")
            base_dataset = await crud.dataset_2d.get(db, id=base_dataset_id)
            if not base_dataset:
                raise NotFoundError(f"Dataset {base_dataset_id} not found")

            images = await self._load_dataset_images(db, base_dataset_id)
            await sse_logger.info(f"이미지 로드 완료: {len(images)}개")

            # Step 2: Load model as ART estimator
            await sse_logger.status("모델 로딩 중...")
            estimator, input_size = await self._load_art_estimator(db, model_id)
            await sse_logger.info("모델 로딩 완료")

            # Step 3: Create ART attack object
            await sse_logger.status(f"{attack_method.upper()} 공격 객체 생성 중...")

            # Normalize epsilon to [0, 1] scale (ART expects clip_values=(0, 255))
            # Since estimator has clip_values=(0, 255), eps should be in [0, 255]
            eps_normalized = epsilon  # Keep in [0, 255] scale

            if attack_method == "fgsm":
                attack = FastGradientMethod(
                    estimator=estimator,
                    norm=np.inf,
                    eps=eps_normalized,
                    targeted=False,
                    batch_size=1,  # Process one image at a time
                )
                await sse_logger.info(f"FGSM 생성: epsilon={epsilon}")
            else:  # pgd
                # Normalize alpha as well
                alpha_normalized = alpha

                attack = ProjectedGradientDescent(
                    estimator=estimator,
                    norm=np.inf,
                    eps=eps_normalized,
                    eps_step=alpha_normalized,
                    max_iter=iterations,
                    targeted=False,
                    num_random_init=0,
                    batch_size=1,
                    verbose=False,
                )
                await sse_logger.info(f"PGD 생성: epsilon={epsilon}, alpha={alpha}, iterations={iterations}")

            # Step 4: Apply attack to all images
            await sse_logger.status("이미지에 공격 적용 중...")
            attacked_images = []
            failed_count = 0

            # Use thread pool to avoid blocking event loop during attack generation
            import asyncio
            import concurrent.futures

            loop = asyncio.get_event_loop()

            for idx, img_data in enumerate(images):
                try:
                    # Progress update - Send BEFORE attacking (shows current image being processed)
                    await sse_logger.progress(
                        f"노이즈 공격 적용 중... ({idx + 1}/{len(images)})",
                        processed=idx,  # Show completed count
                        total=len(images),
                        successful=len(attacked_images),
                        failed=failed_count,
                    )

                    # Load image
                    img = img_data["image"]  # numpy array (H, W, C) in RGB

                    # Resize to model input size if needed (following notebook approach)
                    model_height, model_width = input_size[0], input_size[1]
                    if img.shape[0] != model_height or img.shape[1] != model_width:
                        from PIL import Image
                        img_pil = Image.fromarray(img.astype(np.uint8))
                        img_pil = img_pil.resize((model_width, model_height), Image.BICUBIC)
                        img = np.array(img_pil).astype(np.float32)

                    # Convert to NCHW format for PyTorch
                    # ART expects (N, C, H, W) when channels_first=True
                    x = img.transpose(2, 0, 1)  # (H, W, C) -> (C, H, W)
                    x = np.expand_dims(x, axis=0).astype(np.float32)  # (C, H, W) -> (1, C, H, W)

                    # Generate adversarial example in thread pool to avoid blocking
                    def generate_adv():
                        return attack.generate(x=x)

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        x_adv = await loop.run_in_executor(executor, generate_adv)

                    # Convert back to HWC format
                    # Output: (1, C, H, W) -> (H, W, C)
                    adv_img = x_adv[0].transpose(1, 2, 0)  # (C, H, W) -> (H, W, C)
                    adv_img = np.clip(adv_img, 0, 255).astype(np.uint8)

                    attacked_images.append({
                        "image": adv_img,
                        "original_file_name": img_data["file_name"],
                        "original_id": img_data["id"],
                    })

                    # Send progress update AFTER completing the image
                    await sse_logger.progress(
                        f"노이즈 공격 완료... ({idx + 1}/{len(images)})",
                        processed=idx + 1,  # Show completed count
                        total=len(images),
                        successful=len(attacked_images),
                        failed=failed_count,
                    )

                except Exception as e:
                    logger.error(f"Failed to attack image {idx}: {e}", exc_info=True)
                    failed_count += 1
                    await sse_logger.warning(f"이미지 {idx} 공격 실패: {str(e)}")

            if not attacked_images:
                raise ValidationError("All images failed to be attacked")

            await sse_logger.info(f"공격 완료: 성공 {len(attacked_images)}, 실패 {failed_count}")

            # Step 5: Create output dataset
            await sse_logger.status("공격된 이미지 저장 중...")

            output_dataset_name = f"{attack_name}_output"
            output_dataset_path = self.attack_datasets_dir / f"{attack_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            output_dataset_path.mkdir(parents=True, exist_ok=True)

            output_dataset = await crud.dataset_2d.create(
                db,
                obj_in=schemas.Dataset2DCreate(
                    name=output_dataset_name,
                    description=f"Output dataset from {attack_method.upper()} attack",
                    storage_path=str(output_dataset_path.relative_to(self.storage_root)),
                ),
                owner_id=current_user_id,
            )

            # Save images and create image records
            for img_data in attacked_images:
                # Save image
                file_name = f"adv_{img_data['original_file_name']}"
                img_path = output_dataset_path / file_name

                # Convert RGB to BGR for OpenCV
                img_bgr = cv2.cvtColor(img_data["image"], cv2.COLOR_RGB2BGR)
                cv2.imwrite(str(img_path), img_bgr)

                # Create Image2D record
                height, width = img_data["image"].shape[:2]
                await crud.image_2d.create(
                    db,
                    obj_in=schemas.ImageCreate(
                        dataset_id=output_dataset.id,
                        file_name=file_name,
                        storage_key=str(img_path.relative_to(self.storage_root)),
                        width=width,
                        height=height,
                        mime_type="image/png",
                    ),
                    owner_id=current_user_id,
                )

            await db.commit()
            await sse_logger.info(f"저장 완료: {len(attacked_images)}개 이미지")

            # Step 6: Create AttackDataset2D record
            await sse_logger.status("공격 데이터셋 레코드 생성 중...")

            attack_dataset = await crud.attack_dataset_2d.create(
                db,
                obj_in=schemas.AttackDataset2DCreate(
                    name=attack_name,
                    description=f"{attack_method.upper()} attack with epsilon={epsilon}",
                    attack_type=AttackType.NOISE,
                    target_model_id=model_id,
                    base_dataset_id=base_dataset_id,
                    target_class=None,  # Noise attacks don't target specific class
                    patch_id=None,
                    parameters={
                        "attack_method": attack_method,
                        "epsilon": epsilon,
                        "alpha": alpha,
                        "iterations": iterations,
                        "processed_images": len(attacked_images),
                        "failed_images": failed_count,
                        "output_dataset_id": str(output_dataset.id),
                        "storage_path": str(output_dataset_path),
                    },
                ),
                owner_id=current_user_id,
            )

            await db.commit()

            # Note: No need to cleanup estimator since we created it directly with ART, not via model_inference_service

            await sse_logger.success(
                "공격 데이터셋 생성 완료!",
                attack_dataset_id=str(attack_dataset.id),
                output_dataset_id=str(output_dataset.id),
                processed=len(attacked_images),
                failed=failed_count,
            )

            # Send complete event to close SSE stream
            if session_id:
                await self.sse_manager.send_event(session_id, {
                    "type": "complete",
                    "message": "공격 데이터셋 생성 완료!",
                    "attack_dataset_id": str(attack_dataset.id),
                    "output_dataset_id": str(output_dataset.id),
                    "processed": len(attacked_images),
                    "failed": failed_count,
                })

            return schemas.AttackDataset2DResponse.model_validate(attack_dataset), output_dataset.id

        except Exception as e:
            error_message = f"공격 데이터셋 생성 실패: {str(e)}"
            await sse_logger.error(error_message)
            logger.error(f"Error creating noise attack dataset: {e}", exc_info=True)

            # Send error event to close SSE stream
            if session_id:
                await self.sse_manager.send_event(session_id, {
                    "type": "error",
                    "message": error_message,
                })
            raise

    async def _load_dataset_images(
        self,
        db: AsyncSession,
        dataset_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Load all images from a dataset.

        Returns:
            List of dicts with keys: id, file_name, image (numpy array RGB)
        """
        # Get all images from dataset
        images_db = await crud.image_2d.get_by_dataset(db, dataset_id=dataset_id)

        if not images_db:
            raise ValidationError(f"Dataset {dataset_id} has no images")

        loaded_images = []
        for img_record in images_db:
            # Construct full path
            img_path = self.storage_root / img_record.storage_key

            if not img_path.exists():
                logger.warning(f"Image file not found: {img_path}")
                continue

            # Load image
            img_bgr = cv2.imread(str(img_path))
            if img_bgr is None:
                logger.warning(f"Failed to load image: {img_path}")
                continue

            # Convert BGR to RGB
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

            loaded_images.append({
                "id": img_record.id,
                "file_name": img_record.file_name,
                "image": img_rgb,  # (H, W, C) RGB uint8
            })

        return loaded_images

    async def _load_art_estimator(
        self,
        db: AsyncSession,
        model_id: UUID,
    ):
        """
        Load model from DB and create a real ART estimator (for attacks).

        Returns:
            ART-compatible estimator (PyTorchYolo)
        """
        import torch
        from ultralytics import YOLO

        # Get model from DB
        model = await crud.od_model.get(db, id=model_id)
        if not model:
            raise ValidationError(f"Model {model_id} not found")

        # Get weights artifact
        if not model.artifacts:
            raise ValidationError(f"Model {model_id} has no artifacts")

        weights_artifact = next((a for a in model.artifacts if a.artifact_type == "weights"), None)
        if not weights_artifact:
            raise ValidationError(f"Model {model_id} has no weights artifact")

        # Get model path
        from pathlib import Path
        model_path = Path(weights_artifact.storage_key)
        if not model_path.exists():
            model_path = Path(weights_artifact.storage_path)
            if not model_path.exists():
                raise ValidationError(f"Model file not found: {model_path}")

        # Get class names from labelmap
        class_names = ["person"]  # Default
        if model.labelmap:
            class_names = [model.labelmap[str(i)] for i in sorted([int(k) for k in model.labelmap.keys()])]

        # Get input size
        input_size = [640, 640]  # Default
        if model.input_spec and "shape" in model.input_spec:
            input_size = model.input_spec["shape"][:2]

        # Load YOLO model using ultralytics
        yolo_model = YOLO(str(model_path))

        # Detect model name from path
        filename = str(model_path).lower()
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

        # Create ART PyTorchYolo estimator
        # This is the REAL ART estimator, not our custom one
        # is_ultralytics=True is REQUIRED for YOLOv8+
        # model_name is also required when using is_ultralytics=True
        # channels_first=True AND provide NCHW input (C, H, W format)
        estimator = ARTPyTorchYolo(
            model=yolo_model.model,
            input_shape=(3, *input_size),  # (C, H, W)
            channels_first=True,  # PyTorch uses NCHW format
            clip_values=(0, 255),
            attack_losses=("loss_total",),
            device_type="cpu",  # Use CPU for consistency
            is_ultralytics=True,  # REQUIRED for YOLOv8+
            model_name=model_name,  # Required with is_ultralytics
        )

        logger.info(f"ART estimator loaded: {type(estimator)}")
        return estimator, input_size


# Global instance
noise_attack_service = NoiseAttackService()
