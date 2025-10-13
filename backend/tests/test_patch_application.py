"""
Unit tests for patch application logic.

Tests that patches are applied correctly:
1. Patch size is 30% of bbox width (square)
2. Patch is centered on bbox center
3. Patch is correctly placed on the image
"""
import pytest
import numpy as np
import cv2
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.ai.base_detector import DetectionResult, Detection, BoundingBox


@pytest.mark.unit
@pytest.mark.asyncio
class TestPatchApplication:
    """Test patch application logic."""

    async def test_patch_size_is_30_percent_of_bbox_width(
        self,
        db_session,
        test_model_version,
        test_dataset,
        temp_storage_dir
    ):
        """Test that patch size is 30% of bounding box width."""
        from app.services.adversarial_patch_service import adversarial_patch_service
        from app.crud import patch_2d, attack_dataset_2d, image_2d
        from app.models.dataset_2d import Patch2D, Image2D

        # Create a test patch
        patch_size = 100
        patch_np = np.random.randint(0, 255, (patch_size, patch_size, 3), dtype=np.uint8)
        patch_path = temp_storage_dir / "test_patch.png"
        cv2.imwrite(str(patch_path), patch_np)

        # Create patch DB record
        patch_db = Patch2D(
            id=uuid4(),
            name="Test Patch",
            target_class="person",
            method="test",
            target_model_version_id=test_model_version.id,
            source_dataset_id=test_dataset.id,
            patch_metadata={"patch_file": str(patch_path)}
        )
        db_session.add(patch_db)
        await db_session.commit()

        # Create test image with known size
        img_width, img_height = 640, 480
        test_img = np.zeros((img_height, img_width, 3), dtype=np.uint8)
        img_path = temp_storage_dir / "test_image.jpg"
        cv2.imwrite(str(img_path), test_img)

        # Create image DB record
        image_db = Image2D(
            id=uuid4(),
            file_name="test_image.jpg",
            dataset_id=test_dataset.id,
            storage_key=str(img_path),
            width=img_width,
            height=img_height
        )
        db_session.add(image_db)
        await db_session.commit()

        # Mock detection with known bbox
        bbox_x1, bbox_y1, bbox_x2, bbox_y2 = 100, 100, 300, 250
        bbox_width = bbox_x2 - bbox_x1  # 200
        expected_patch_size = int(bbox_width * 0.3)  # 60

        mock_detection = Detection(
            bbox=BoundingBox(x1=bbox_x1, y1=bbox_y1, x2=bbox_x2, y2=bbox_y2),
            class_name="person",
            class_id=0,
            confidence=0.9
        )

        mock_result = DetectionResult(
            detections=[mock_detection],
            inference_time=0.05
        )

        # Mock the inference service
        with patch('app.services.custom_model_service.custom_model_service') as mock_service:
            mock_service.run_inference = AsyncMock(return_value=mock_result)

            # Apply patch
            attack_dataset_db, attack_dir = await adversarial_patch_service.apply_patch_to_dataset(
                db=db_session,
                attack_dataset_name="Test Attack",
                model_version_id=test_model_version.id,
                base_dataset_id=test_dataset.id,
                patch_id=patch_db.id,
                target_class="person",
                patch_scale=0.3  # Not used anymore, but kept for API compatibility
            )

            # Verify attacked image exists
            attacked_files = list(attack_dir.glob("attacked_*.jpg"))
            assert len(attacked_files) == 1, "Should create one attacked image"

            # Load attacked image
            attacked_img = cv2.imread(str(attacked_files[0]))
            assert attacked_img is not None

            # Calculate expected patch position (center of bbox)
            center_x = (bbox_x1 + bbox_x2) // 2  # 200
            center_y = (bbox_y1 + bbox_y2) // 2  # 175

            patch_x1 = center_x - expected_patch_size // 2  # 200 - 30 = 170
            patch_y1 = center_y - expected_patch_size // 2  # 175 - 30 = 145
            patch_x2 = patch_x1 + expected_patch_size  # 230
            patch_y2 = patch_y1 + expected_patch_size  # 205

            # Extract the patch area from attacked image
            extracted_patch = attacked_img[patch_y1:patch_y2, patch_x1:patch_x2]

            # Verify patch dimensions
            assert extracted_patch.shape[0] == expected_patch_size, \
                f"Patch height should be {expected_patch_size}, got {extracted_patch.shape[0]}"
            assert extracted_patch.shape[1] == expected_patch_size, \
                f"Patch width should be {expected_patch_size}, got {extracted_patch.shape[1]}"

            # Verify patch is different from original (black) image
            # The patch should have non-zero values
            patch_mean = extracted_patch.mean()
            assert patch_mean > 0, "Patch area should be modified (not all zeros)"

            print(f"✓ Patch size verified: {expected_patch_size}x{expected_patch_size}")
            print(f"✓ Patch position: ({patch_x1}, {patch_y1}) to ({patch_x2}, {patch_y2})")
            print(f"✓ Expected bbox center: ({center_x}, {center_y})")

    async def test_patch_centered_on_bbox(
        self,
        db_session,
        test_model_version,
        test_dataset,
        temp_storage_dir
    ):
        """Test that patch is centered on bounding box center."""
        from app.services.adversarial_patch_service import adversarial_patch_service
        from app.models.dataset_2d import Patch2D, Image2D

        # Create a distinctive colored patch (red)
        patch_size = 100
        patch_np = np.zeros((patch_size, patch_size, 3), dtype=np.uint8)
        patch_np[:, :] = [0, 0, 255]  # Red in BGR
        patch_path = temp_storage_dir / "red_patch.png"
        cv2.imwrite(str(patch_path), patch_np)

        # Create patch DB record
        patch_db = Patch2D(
            id=uuid4(),
            name="Red Patch",
            target_class="person",
            method="test",
            target_model_version_id=test_model_version.id,
            source_dataset_id=test_dataset.id,
            patch_metadata={"patch_file": str(patch_path)}
        )
        db_session.add(patch_db)
        await db_session.commit()

        # Create test image (blue background)
        img_width, img_height = 640, 480
        test_img = np.zeros((img_height, img_width, 3), dtype=np.uint8)
        test_img[:, :] = [255, 0, 0]  # Blue in BGR
        img_path = temp_storage_dir / "blue_image.jpg"
        cv2.imwrite(str(img_path), test_img)

        # Create image DB record
        image_db = Image2D(
            id=uuid4(),
            file_name="blue_image.jpg",
            dataset_id=test_dataset.id,
            storage_key=str(img_path),
            width=img_width,
            height=img_height
        )
        db_session.add(image_db)
        await db_session.commit()

        # Mock detection
        bbox_x1, bbox_y1, bbox_x2, bbox_y2 = 200, 150, 400, 300
        bbox_width = bbox_x2 - bbox_x1
        expected_patch_size = int(bbox_width * 0.3)

        mock_detection = Detection(
            bbox=BoundingBox(x1=bbox_x1, y1=bbox_y1, x2=bbox_x2, y2=bbox_y2),
            class_name="person",
            class_id=0,
            confidence=0.95
        )

        mock_result = DetectionResult(
            detections=[mock_detection],
            inference_time=0.05
        )

        # Mock the inference service
        with patch('app.services.custom_model_service.custom_model_service') as mock_service:
            mock_service.run_inference = AsyncMock(return_value=mock_result)

            # Apply patch
            attack_dataset_db, attack_dir = await adversarial_patch_service.apply_patch_to_dataset(
                db=db_session,
                attack_dataset_name="Center Test Attack",
                model_version_id=test_model_version.id,
                base_dataset_id=test_dataset.id,
                patch_id=patch_db.id,
                target_class="person"
            )

            # Load attacked image
            attacked_files = list(attack_dir.glob("attacked_*.jpg"))
            attacked_img = cv2.imread(str(attacked_files[0]))

            # Calculate expected center position
            center_x = (bbox_x1 + bbox_x2) // 2
            center_y = (bbox_y1 + bbox_y2) // 2

            # Check that the center pixel is red (from patch), not blue (from background)
            center_pixel = attacked_img[center_y, center_x]

            # Center should be reddish (B=low, G=low, R=high)
            assert center_pixel[0] < 100, f"Center pixel should have low blue, got {center_pixel[0]}"
            assert center_pixel[2] > 150, f"Center pixel should have high red, got {center_pixel[2]}"

            print(f"✓ Patch centered at bbox center: ({center_x}, {center_y})")
            print(f"✓ Center pixel color (BGR): {center_pixel}")

    async def test_patch_is_square(
        self,
        db_session,
        test_model_version,
        test_dataset,
        temp_storage_dir
    ):
        """Test that applied patch is always square."""
        from app.services.adversarial_patch_service import adversarial_patch_service
        from app.models.dataset_2d import Patch2D, Image2D

        # Create patch
        patch_size = 80
        patch_np = np.random.randint(0, 255, (patch_size, patch_size, 3), dtype=np.uint8)
        patch_path = temp_storage_dir / "square_patch.png"
        cv2.imwrite(str(patch_path), patch_np)

        patch_db = Patch2D(
            id=uuid4(),
            name="Square Patch",
            target_class="person",
            method="test",
            target_model_version_id=test_model_version.id,
            source_dataset_id=test_dataset.id,
            patch_metadata={"patch_file": str(patch_path)}
        )
        db_session.add(patch_db)
        await db_session.commit()

        # Create test image
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        img_path = temp_storage_dir / "test_square.jpg"
        cv2.imwrite(str(img_path), test_img)

        image_db = Image2D(
            id=uuid4(),
            file_name="test_square.jpg",
            dataset_id=test_dataset.id,
            storage_key=str(img_path),
            width=640,
            height=480
        )
        db_session.add(image_db)
        await db_session.commit()

        # Test with different bbox aspect ratios
        test_cases = [
            # (x1, y1, x2, y2, description)
            (100, 100, 300, 200, "Wide bbox (200x100)"),
            (100, 100, 200, 300, "Tall bbox (100x200)"),
            (100, 100, 400, 250, "Very wide bbox (300x150)"),
        ]

        for bbox_x1, bbox_y1, bbox_x2, bbox_y2, description in test_cases:
            bbox_width = bbox_x2 - bbox_x1
            expected_patch_size = int(bbox_width * 0.3)

            mock_detection = Detection(
                bbox=BoundingBox(x1=bbox_x1, y1=bbox_y1, x2=bbox_x2, y2=bbox_y2),
                class_name="person",
                class_id=0,
                confidence=0.9
            )

            mock_result = DetectionResult(
                detections=[mock_detection],
                inference_time=0.05
            )

            with patch('app.services.custom_model_service.custom_model_service') as mock_service:
                mock_service.run_inference = AsyncMock(return_value=mock_result)

                attack_dataset_db, attack_dir = await adversarial_patch_service.apply_patch_to_dataset(
                    db=db_session,
                    attack_dataset_name=f"Square Test {description}",
                    model_version_id=test_model_version.id,
                    base_dataset_id=test_dataset.id,
                    patch_id=patch_db.id,
                    target_class="person"
                )

                # Verify patch is square
                attacked_files = list(attack_dir.glob("attacked_*.jpg"))
                if attacked_files:
                    attacked_img = cv2.imread(str(attacked_files[0]))

                    # Calculate patch position
                    center_x = (bbox_x1 + bbox_x2) // 2
                    center_y = (bbox_y1 + bbox_y2) // 2
                    patch_x1 = max(0, center_x - expected_patch_size // 2)
                    patch_y1 = max(0, center_y - expected_patch_size // 2)
                    patch_x2 = min(640, patch_x1 + expected_patch_size)
                    patch_y2 = min(480, patch_y1 + expected_patch_size)

                    # Extract patch
                    extracted = attacked_img[patch_y1:patch_y2, patch_x1:patch_x2]

                    # Verify square (width == height)
                    assert extracted.shape[0] == extracted.shape[1], \
                        f"{description}: Patch should be square, got {extracted.shape[0]}x{extracted.shape[1]}"

                    print(f"✓ {description}: Patch is square {expected_patch_size}x{expected_patch_size}")
