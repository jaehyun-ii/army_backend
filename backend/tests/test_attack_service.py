"""
Comprehensive tests for AttackService, InferenceService, and DatasetService.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4, UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.attack_service import AttackService, InferenceService, DatasetService
from app.models.dataset_2d import AttackType, AttackDataset2D, Image2D, Dataset2D, Patch2D
from app.core.exceptions import NotFoundError, ValidationError


# ==================== AttackService Tests ====================

class TestAttackService:
    """Test suite for AttackService."""

    @pytest.fixture
    def attack_service(self):
        """Create AttackService instance."""
        return AttackService()

    @pytest.fixture
    def mock_patch_attack(self):
        """Mock patch attack dataset."""
        attack_id = uuid4()
        patch_id = uuid4()
        base_dataset_id = uuid4()

        attack = Mock(spec=AttackDataset2D)
        attack.id = attack_id
        attack.name = "Test Patch Attack"
        attack.attack_type = AttackType.PATCH
        attack.patch_id = patch_id
        attack.base_dataset_id = base_dataset_id
        attack.storage_path = "/storage/attacks/test"
        attack.method = "rp2_attack"
        attack.hyperparameters = {}
        attack.attack_metadata = {"total_images": 10}
        attack.created_at = datetime.now(timezone.utc)

        return attack

    @pytest.fixture
    def mock_noise_attack(self):
        """Mock noise attack dataset."""
        attack_id = uuid4()
        base_dataset_id = uuid4()

        attack = Mock(spec=AttackDataset2D)
        attack.id = attack_id
        attack.name = "Test Noise Attack"
        attack.attack_type = AttackType.NOISE
        attack.patch_id = None
        attack.base_dataset_id = base_dataset_id
        attack.storage_path = "/storage/attacks/noise"
        attack.method = "fgsm"
        attack.hyperparameters = {"epsilon": 0.03}
        attack.attack_metadata = {"total_images": 15}
        attack.created_at = datetime.now(timezone.utc)

        return attack

    @pytest.fixture
    def mock_patch(self):
        """Mock patch object."""
        patch_id = uuid4()

        patch = Mock(spec=Patch2D)
        patch.id = patch_id
        patch.name = "Test Patch"
        patch.target_class = "person"

        return patch

    @pytest.fixture
    def mock_images(self):
        """Mock image list."""
        images = []
        for i in range(5):
            img = Mock(spec=Image2D)
            img.id = uuid4()
            img.file_name = f"image_{i}.jpg"
            images.append(img)
        return images

    @pytest.mark.asyncio
    async def test_execute_patch_attack_success(
        self, attack_service, mock_patch_attack, mock_patch, mock_images
    ):
        """Test successful patch attack execution."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock CRUD operations
        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.attack_dataset_2d.get = AsyncMock(return_value=mock_patch_attack)
            mock_crud.patch_2d.get = AsyncMock(return_value=mock_patch)
            mock_crud.image_2d.get_by_dataset = AsyncMock(return_value=mock_images)

            # Execute attack
            result = await attack_service.execute_2d_attack(
                db=mock_db,
                attack_id=mock_patch_attack.id
            )

            # Assertions
            assert result["attack_type"] == "patch"
            assert result["patch_id"] == str(mock_patch.id)
            assert result["patch_name"] == mock_patch.name
            assert result["target_class"] == mock_patch.target_class
            assert result["processed_images"] == 5
            assert result["status"] == "completed"

            # Verify CRUD calls
            mock_crud.attack_dataset_2d.get.assert_called_once()
            mock_crud.patch_2d.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_noise_attack_success(
        self, attack_service, mock_noise_attack, mock_images
    ):
        """Test successful noise attack execution."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.attack_dataset_2d.get = AsyncMock(return_value=mock_noise_attack)
            mock_crud.image_2d.get_by_dataset = AsyncMock(return_value=mock_images)

            # Execute attack
            result = await attack_service.execute_2d_attack(
                db=mock_db,
                attack_id=mock_noise_attack.id
            )

            # Assertions
            assert result["attack_type"] == "noise"
            assert result["method"] == "fgsm"
            assert result["processed_images"] == 5
            assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_attack_not_found(self, attack_service):
        """Test attack execution with non-existent attack."""
        mock_db = AsyncMock(spec=AsyncSession)
        fake_id = uuid4()

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.attack_dataset_2d.get = AsyncMock(return_value=None)

            # Should raise NotFoundError
            with pytest.raises(NotFoundError) as exc_info:
                await attack_service.execute_2d_attack(
                    db=mock_db,
                    attack_id=fake_id
                )

            assert f"Attack dataset {fake_id}" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_attack_no_target_images(
        self, attack_service, mock_patch_attack
    ):
        """Test attack execution with no target images."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.attack_dataset_2d.get = AsyncMock(return_value=mock_patch_attack)
            mock_crud.image_2d.get_by_dataset = AsyncMock(return_value=[])

            # Should raise ValidationError
            with pytest.raises(ValidationError) as exc_info:
                await attack_service.execute_2d_attack(
                    db=mock_db,
                    attack_id=mock_patch_attack.id
                )

            assert "No target images" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_patch_attack_missing_patch_id(
        self, attack_service, mock_patch_attack, mock_images
    ):
        """Test patch attack execution with missing patch_id."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_patch_attack.patch_id = None  # No patch_id

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.attack_dataset_2d.get = AsyncMock(return_value=mock_patch_attack)
            mock_crud.image_2d.get_by_dataset = AsyncMock(return_value=mock_images)

            # Should raise ValidationError
            with pytest.raises(ValidationError) as exc_info:
                await attack_service.execute_2d_attack(
                    db=mock_db,
                    attack_id=mock_patch_attack.id
                )

            assert "requires patch_id" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_calculate_metrics_with_evaluations(self, attack_service, mock_patch_attack):
        """Test metrics calculation with pre/post evaluations."""
        mock_db = AsyncMock(spec=AsyncSession)

        pre_eval_id = uuid4()
        post_eval_id = uuid4()

        # Mock evaluations
        pre_eval = Mock()
        pre_eval.metrics_summary = {
            "mAP_50": 0.75,
            "precision": 0.80,
            "recall": 0.70
        }

        post_eval = Mock()
        post_eval.metrics_summary = {
            "mAP_50": 0.45,
            "precision": 0.50,
            "recall": 0.40
        }

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.attack_dataset_2d.get = AsyncMock(return_value=mock_patch_attack)
            mock_crud.evaluation_run.get = AsyncMock(
                side_effect=[pre_eval, post_eval]
            )

            # Calculate metrics
            metrics = await attack_service.calculate_attack_metrics(
                db=mock_db,
                attack_id=mock_patch_attack.id,
                pre_attack_eval_id=pre_eval_id,
                post_attack_eval_id=post_eval_id
            )

            # Assertions
            assert metrics["pre_attack_mAP_50"] == 0.75
            assert metrics["post_attack_mAP_50"] == 0.45
            assert metrics["mAP_50_drop"] == pytest.approx(0.30)
            assert metrics["mAP_50_drop_percentage"] == pytest.approx(40.0)
            assert metrics["precision_drop"] == pytest.approx(0.30)
            assert metrics["recall_drop"] == pytest.approx(0.30)
            assert metrics["attack_effectiveness"] == pytest.approx(0.40)
            assert metrics["status"] == "completed"

    @pytest.mark.asyncio
    async def test_calculate_metrics_without_evaluations(
        self, attack_service, mock_patch_attack
    ):
        """Test metrics calculation without evaluations (basic stats)."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.attack_dataset_2d.get = AsyncMock(return_value=mock_patch_attack)

            # Calculate metrics without evaluation IDs
            metrics = await attack_service.calculate_attack_metrics(
                db=mock_db,
                attack_id=mock_patch_attack.id
            )

            # Assertions
            assert metrics["attack_id"] == str(mock_patch_attack.id)
            assert metrics["attack_type"] == AttackType.PATCH.value
            assert metrics["total_images"] == 10
            assert metrics["method"] == "rp2_attack"
            assert metrics["status"] == "basic_stats_only"

    @pytest.mark.asyncio
    async def test_get_attack_summary_with_patch(
        self, attack_service, mock_patch_attack, mock_patch
    ):
        """Test getting attack summary with patch."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock base dataset
        base_dataset = Mock(spec=Dataset2D)
        base_dataset.id = mock_patch_attack.base_dataset_id
        base_dataset.name = "Base Dataset"

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.attack_dataset_2d.get = AsyncMock(return_value=mock_patch_attack)
            mock_crud.dataset_2d.get = AsyncMock(return_value=base_dataset)
            mock_crud.patch_2d.get = AsyncMock(return_value=mock_patch)

            # Get summary
            summary = await attack_service.get_attack_summary(
                db=mock_db,
                attack_id=mock_patch_attack.id
            )

            # Assertions
            assert summary["id"] == str(mock_patch_attack.id)
            assert summary["name"] == mock_patch_attack.name
            assert summary["attack_type"] == AttackType.PATCH.value
            assert summary["method"] == "rp2_attack"
            assert summary["base_dataset"]["name"] == "Base Dataset"
            assert summary["patch"]["name"] == mock_patch.name
            assert summary["patch"]["target_class"] == "person"

    @pytest.mark.asyncio
    async def test_get_attack_summary_noise_attack(
        self, attack_service, mock_noise_attack
    ):
        """Test getting attack summary for noise attack (no patch)."""
        mock_db = AsyncMock(spec=AsyncSession)

        base_dataset = Mock(spec=Dataset2D)
        base_dataset.id = mock_noise_attack.base_dataset_id
        base_dataset.name = "Base Dataset"

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.attack_dataset_2d.get = AsyncMock(return_value=mock_noise_attack)
            mock_crud.dataset_2d.get = AsyncMock(return_value=base_dataset)
            mock_crud.patch_2d.get = AsyncMock(return_value=None)

            # Get summary
            summary = await attack_service.get_attack_summary(
                db=mock_db,
                attack_id=mock_noise_attack.id
            )

            # Assertions
            assert summary["attack_type"] == AttackType.NOISE.value
            assert summary["method"] == "fgsm"
            assert summary["patch"] is None


# ==================== InferenceService Tests ====================

class TestInferenceService:
    """Test suite for InferenceService."""

    @pytest.fixture
    def inference_service(self):
        """Create InferenceService instance."""
        return InferenceService()

    @pytest.fixture
    def mock_model_version(self):
        """Mock model version."""
        version = Mock()
        version.id = uuid4()
        version.version_number = "1.0.0"
        return version

    @pytest.fixture
    def mock_inference_images(self):
        """Mock images with storage keys."""
        images = []
        for i in range(3):
            img = Mock(spec=Image2D)
            img.id = uuid4()
            img.file_name = f"test_{i}.jpg"
            img.storage_key = f"/tmp/test_{i}.jpg"
            images.append(img)
        return images

    @pytest.mark.asyncio
    async def test_run_inference_success(
        self, inference_service, mock_model_version, mock_inference_images
    ):
        """Test successful inference execution."""
        mock_db = AsyncMock(spec=AsyncSession)
        image_ids = [img.id for img in mock_inference_images]

        # Mock detection result
        mock_detection = Mock()
        mock_detection.class_id = 0
        mock_detection.class_name = "person"
        mock_detection.confidence = 0.95
        mock_detection.bbox = Mock(x1=10, y1=20, x2=100, y2=200)

        mock_inference_result = Mock()
        mock_inference_result.detections = [mock_detection]
        mock_inference_result.inference_time_ms = 50

        with patch('app.services.attack_service.crud') as mock_crud, \
             patch.object(inference_service.custom_model_service, 'get_model_info',
                         return_value={"is_loaded": True}), \
             patch.object(inference_service.custom_model_service, 'run_inference',
                         return_value=mock_inference_result), \
             patch('cv2.imread', return_value=Mock()), \
             patch('app.services.attack_service.Path') as mock_path:

            mock_crud.od_model_version.get = AsyncMock(return_value=mock_model_version)
            mock_crud.image_2d.get = AsyncMock(side_effect=mock_inference_images)

            # Mock file operations
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance

            # Run inference
            results = await inference_service.run_inference(
                db=mock_db,
                model_version_id=mock_model_version.id,
                image_ids=image_ids
            )

            # Assertions
            assert len(results) == 3
            for result in results:
                assert result["status"] == "success"
                assert len(result["detections"]) == 1
                assert result["detections"][0]["class_name"] == "person"
                assert result["inference_time_ms"] == 50

    @pytest.mark.asyncio
    async def test_run_inference_model_not_found(self, inference_service):
        """Test inference with non-existent model."""
        mock_db = AsyncMock(spec=AsyncSession)
        fake_model_id = uuid4()

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.od_model_version.get = AsyncMock(return_value=None)

            # Should raise NotFoundError
            with pytest.raises(NotFoundError):
                await inference_service.run_inference(
                    db=mock_db,
                    model_version_id=fake_model_id,
                    image_ids=[uuid4()]
                )

    @pytest.mark.asyncio
    async def test_batch_inference_success(
        self, inference_service, mock_model_version, mock_inference_images
    ):
        """Test successful batch inference."""
        mock_db = AsyncMock(spec=AsyncSession)
        dataset_id = uuid4()

        # Mock detection result
        mock_detection = Mock()
        mock_detection.class_id = 0
        mock_detection.class_name = "person"
        mock_detection.confidence = 0.95
        mock_detection.bbox = Mock(x1=10, y1=20, x2=100, y2=200)

        mock_inference_result = Mock()
        mock_inference_result.detections = [mock_detection]
        mock_inference_result.inference_time_ms = 50

        with patch('app.services.attack_service.crud') as mock_crud, \
             patch.object(inference_service.custom_model_service, 'get_model_info',
                         return_value={"is_loaded": True}), \
             patch.object(inference_service.custom_model_service, 'run_inference',
                         return_value=mock_inference_result), \
             patch('cv2.imread', return_value=Mock()), \
             patch('app.services.attack_service.Path') as mock_path:

            mock_crud.od_model_version.get = AsyncMock(return_value=mock_model_version)
            mock_crud.image_2d.get_by_dataset = AsyncMock(return_value=mock_inference_images)
            mock_crud.image_2d.get = AsyncMock(side_effect=mock_inference_images * 10)

            # Mock file operations
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance

            # Run batch inference
            result = await inference_service.batch_inference(
                db=mock_db,
                model_version_id=mock_model_version.id,
                dataset_id=dataset_id,
                batch_size=2
            )

            # Assertions
            assert result["dataset_id"] == str(dataset_id)
            assert result["total_images"] == 3
            assert result["successful"] == 3
            assert result["failed"] == 0
            assert result["total_detections"] == 3
            assert result["avg_inference_time_ms"] == 50


# ==================== DatasetService Tests ====================

class TestDatasetService:
    """Test suite for DatasetService."""

    @pytest.fixture
    def dataset_service(self):
        """Create DatasetService instance."""
        return DatasetService()

    @pytest.fixture
    def mock_dataset(self):
        """Mock dataset."""
        dataset = Mock(spec=Dataset2D)
        dataset.id = uuid4()
        dataset.name = "Test Dataset"
        dataset.metadata_ = {"classes": ["person", "car"]}
        dataset.created_at = datetime.now(timezone.utc)
        return dataset

    @pytest.mark.asyncio
    async def test_import_images_batch_success(self, dataset_service, mock_dataset):
        """Test successful batch image import."""
        mock_db = AsyncMock(spec=AsyncSession)
        image_paths = ["/tmp/img1.jpg", "/tmp/img2.jpg", "/tmp/img3.jpg"]

        with patch('app.services.attack_service.crud') as mock_crud, \
             patch('app.services.attack_service.Path') as mock_path:

            mock_crud.dataset_2d.get = AsyncMock(return_value=mock_dataset)
            mock_crud.image_2d.create = AsyncMock()

            # Mock Path.exists
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.name = "test.jpg"
            mock_path.return_value = mock_path_instance

            # Import images
            result = await dataset_service.import_images_batch(
                db=mock_db,
                dataset_id=mock_dataset.id,
                image_paths=image_paths
            )

            # Assertions
            assert result == mock_dataset
            assert mock_crud.image_2d.create.call_count == 3

    @pytest.mark.asyncio
    async def test_import_images_dataset_not_found(self, dataset_service):
        """Test image import with non-existent dataset."""
        mock_db = AsyncMock(spec=AsyncSession)
        fake_id = uuid4()

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.dataset_2d.get = AsyncMock(return_value=None)

            # Should raise NotFoundError
            with pytest.raises(NotFoundError):
                await dataset_service.import_images_batch(
                    db=mock_db,
                    dataset_id=fake_id,
                    image_paths=["/tmp/test.jpg"]
                )

    @pytest.mark.asyncio
    async def test_get_dataset_statistics(self, dataset_service, mock_dataset):
        """Test dataset statistics calculation."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock images
        mock_images = []
        for i in range(5):
            img = Mock(spec=Image2D)
            img.width = 640
            img.height = 480
            img.mime_type = "image/jpeg"
            img.storage_key = f"/tmp/img_{i}.jpg"
            mock_images.append(img)

        # Mock SQLAlchemy result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_images

        with patch('app.services.attack_service.crud') as mock_crud, \
             patch('app.services.attack_service.Path') as mock_path:

            mock_crud.dataset_2d.get = AsyncMock(return_value=mock_dataset)
            mock_db.execute = AsyncMock(return_value=mock_result)

            # Mock file size
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.stat.return_value.st_size = 1024 * 100  # 100KB
            mock_path.return_value = mock_path_instance

            # Get statistics
            stats = await dataset_service.get_dataset_statistics(
                db=mock_db,
                dataset_id=mock_dataset.id
            )

            # Assertions
            assert stats["dataset_id"] == str(mock_dataset.id)
            assert stats["total_images"] == 5
            assert stats["avg_width"] == 640
            assert stats["avg_height"] == 480
            assert stats["format_distribution"]["image/jpeg"] == 5
            assert stats["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_class_distribution_from_table(self, dataset_service, mock_dataset):
        """Test class distribution from statistics table."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock class statistics
        mock_stat1 = Mock()
        mock_stat1.class_name = "person"
        mock_stat1.count = 100
        mock_stat1.percentage = 60.0
        mock_stat1.avg_confidence = 0.85

        mock_stat2 = Mock()
        mock_stat2.class_name = "car"
        mock_stat2.count = 67
        mock_stat2.percentage = 40.0
        mock_stat2.avg_confidence = 0.78

        # Mock SQLAlchemy result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_stat1, mock_stat2]

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.dataset_2d.get = AsyncMock(return_value=mock_dataset)
            mock_db.execute = AsyncMock(return_value=mock_result)

            # Get class distribution
            distribution = await dataset_service.get_class_distribution(
                db=mock_db,
                dataset_id=mock_dataset.id
            )

            # Assertions
            assert distribution["dataset_id"] == str(mock_dataset.id)
            assert distribution["total_classes"] == 2
            assert distribution["source"] == "statistics_table"
            assert len(distribution["classes"]) == 2
            assert distribution["classes"][0]["class_name"] == "person"
            assert distribution["classes"][0]["count"] == 100

    @pytest.mark.asyncio
    async def test_get_class_distribution_from_metadata(self, dataset_service, mock_dataset):
        """Test class distribution fallback to metadata."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock empty statistics result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []

        with patch('app.services.attack_service.crud') as mock_crud:
            mock_crud.dataset_2d.get = AsyncMock(return_value=mock_dataset)
            mock_db.execute = AsyncMock(return_value=mock_result)

            # Get class distribution
            distribution = await dataset_service.get_class_distribution(
                db=mock_db,
                dataset_id=mock_dataset.id
            )

            # Assertions
            assert distribution["source"] == "metadata"
            assert distribution["classes"] == ["person", "car"]
            assert distribution["total_classes"] == 2
