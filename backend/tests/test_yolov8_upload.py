"""
Test YOLOv8 model upload and basic operations.
"""
import pytest
import io
from pathlib import Path
from httpx import AsyncClient


@pytest.mark.asyncio
class TestYOLOv8Upload:
    """Test YOLOv8 model upload and inference."""

    async def test_upload_yolov8_model(self, client: AsyncClient, auth_headers):
        """Test uploading YOLOv8n model with adapter and config."""

        # Read files from test_model directory
        test_model_dir = Path(__file__).parent / "test_model"
        weights_path = test_model_dir / "yolov8n.pt"
        config_path = test_model_dir / "yolov8_config.yaml"
        adapter_path = test_model_dir / "yolov8_adapter.py"

        if not weights_path.exists():
            pytest.skip(f"YOLOv8n model file not found at {weights_path}. Download it first.")

        with open(weights_path, "rb") as weights_f, \
             open(config_path, "rb") as config_f, \
             open(adapter_path, "rb") as adapter_f:

            weights_content = weights_f.read()
            config_content = config_f.read()
            adapter_content = adapter_f.read()

        # Upload model
        response = await client.post(
            "/api/v1/custom-models/upload",
            data={
                "model_name": "YOLOv8n",
                "version": "8.3.0",
                "framework": "pytorch",
                "description": "YOLOv8 Nano model pre-trained on COCO"
            },
            files={
                "weights_file": ("yolov8n.pt", io.BytesIO(weights_content), "application/octet-stream"),
                "config_file": ("config.yaml", io.BytesIO(config_content), "text/yaml"),
                "adapter_file": ("adapter.py", io.BytesIO(adapter_content), "text/x-python")
            },
            headers=auth_headers
        )

        print(f"Response status: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 201, f"Upload failed: {response.json()}"

        data = response.json()
        assert "model_id" in data
        assert "version_id" in data

        # Store IDs for other tests
        self.model_version_id = data["version_id"]
        print(f"\n✓ YOLOv8n uploaded - Version ID: {self.model_version_id}")

    async def test_upload_test_dataset(self, client: AsyncClient, auth_headers):
        """Test uploading test dataset with YOLOv8 detections."""

        dataset_path = Path(__file__).parent / "test_dataset"

        if not dataset_path.exists():
            pytest.skip("Test dataset not found")

        response = await client.post(
            "/api/v1/dataset-service/upload-folder",
            json={
                "source_folder": str(dataset_path.absolute()),
                "dataset_name": "YOLOv8 Test Dataset",
                "description": "Test dataset with bus and people"
            },
            headers=auth_headers
        )

        assert response.status_code == 201, f"Dataset upload failed: {response.json()}"

        data = response.json()
        assert "dataset" in data
        assert data["image_count"] > 0

        self.dataset_id = data["dataset"]["id"]
        print(f"\n✓ Dataset uploaded - ID: {self.dataset_id}, Images: {data['image_count']}")
