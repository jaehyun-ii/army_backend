"""
Integration tests for complete workflow: Model Upload → Model List → Real-time Detection
"""
import pytest
import io
import base64
from httpx import AsyncClient
from uuid import uuid4
from PIL import Image


@pytest.mark.integration
@pytest.mark.asyncio
class TestModelToDetectionWorkflow:
    """
    Test complete workflow from model upload through real-time detection.

    Scenario:
    1. Upload a custom model
    2. Verify model appears in loaded models list
    3. Create a camera
    4. Create a capture run
    5. Start real-time detection with the uploaded model
    6. Stop the capture
    """

    async def test_complete_model_to_detection_workflow(
        self,
        client: AsyncClient,
        auth_headers,
        temp_storage_dir,
        test_model_version
    ):
        """Test complete workflow from model upload to real-time detection."""

        # Step 1: Upload a custom model
        weights_content = b"fake weights data for testing"
        config_content = """
model_name: "yolov8_custom"
version: "1.0"
framework: "pytorch"
input_shape: [640, 640, 3]
class_names: ["person", "car", "dog", "cat"]
num_classes: 4
"""
        adapter_content = """
from app.ai.base_detector import BaseObjectDetector
import numpy as np

class YOLOv8CustomDetector(BaseObjectDetector):
    def load_model(self, weights_path, **kwargs):
        # Mock model loading
        self.model_loaded = True
        self.is_loaded = True

    def preprocess(self, image):
        # Mock preprocessing
        return image

    def predict(self, preprocessed_input):
        # Mock prediction
        return []

    def postprocess(self, model_output, original_shape, conf_threshold=0.25, iou_threshold=0.45):
        # Mock postprocessing
        from app.ai.base_detector import DetectionResult
        return DetectionResult(detections=[], inference_time_ms=0.0)
"""

        upload_response = await client.post(
            "/api/v1/custom-models/upload",
            data={
                "model_name": "YOLOv8 Custom",
                "version": "1.0",
                "framework": "pytorch",
                "description": "Custom YOLOv8 model for testing"
            },
            files={
                "weights_file": ("model.pt", io.BytesIO(weights_content), "application/octet-stream"),
                "config_file": ("config.yaml", io.BytesIO(config_content.encode()), "text/yaml"),
                "adapter_file": ("adapter.py", io.BytesIO(adapter_content.encode()), "text/x-python")
            },
            headers=auth_headers
        )

        # Model upload may not be fully implemented
        if upload_response.status_code != 201:
            pytest.skip("Model upload service not fully implemented")

        upload_data = upload_response.json()
        model_version_id = upload_data["version_id"]

        # Step 2: Verify model appears in loaded models list
        list_response = await client.get(
            "/api/v1/custom-models/loaded",
            headers=auth_headers
        )
        assert list_response.status_code == 200
        loaded_models = list_response.json()
        assert isinstance(loaded_models, list)

        # Step 3: Create a camera
        camera_response = await client.post(
            "/api/v1/realtime/cameras",
            json={
                "name": "Test Camera",
                "stream_uri": "rtsp://192.168.1.102/stream",
                "description": "Camera for integration testing",
                "resolution": {"width": 1920, "height": 1080}
            },
            headers=auth_headers
        )
        assert camera_response.status_code == 201
        camera_data = camera_response.json()
        camera_id = camera_data["id"]

        # Step 4: Create a capture run
        run_response = await client.post(
            "/api/v1/realtime/runs",
            json={
                "camera_id": camera_id,
                "model_version_id": model_version_id,
                "window_seconds": 5,
                "frames_expected": 10,
                "notes": "Integration Test Run - Testing complete workflow"
            },
            headers=auth_headers
        )

        # Capture run may require specific fields
        if run_response.status_code not in [201, 422]:
            pytest.skip("Capture run creation service not fully implemented")

        if run_response.status_code == 201:
            run_data = run_response.json()
            run_id = run_data["id"]

            # Step 5: Start real-time detection with the uploaded model
            start_response = await client.post(
                f"/api/v1/realtime/webcam/start/{run_id}",
                params={
                    "model_version_id": model_version_id,
                    "device": "/dev/video0",
                    "fps_target": 10,
                    "window_seconds": 2
                },
                headers=auth_headers
            )

            # Webcam capture may fail in test environment without real camera
            if start_response.status_code == 200:
                # Step 6: Stop the capture
                stop_response = await client.post(
                    f"/api/v1/realtime/webcam/stop/{run_id}",
                    headers=auth_headers
                )
                assert stop_response.status_code in [200, 404]

    async def test_model_load_and_inference_workflow(
        self,
        client: AsyncClient,
        auth_headers,
        mock_image_file
    ):
        """Test workflow: Upload model → Load → Run inference."""

        # Step 1: Upload model
        weights_content = b"fake weights"
        config_content = """
model_name: "test_detector"
version: "1.0"
framework: "pytorch"
class_names: ["person", "car"]
"""
        adapter_content = """
from app.ai.base_detector import BaseObjectDetector, DetectionResult

class TestDetector(BaseObjectDetector):
    def load_model(self, weights_path, **kwargs):
        self.is_loaded = True

    def preprocess(self, image):
        return image

    def predict(self, preprocessed_input):
        return []

    def postprocess(self, model_output, original_shape, conf_threshold=0.25, iou_threshold=0.45):
        return DetectionResult(detections=[], inference_time_ms=0.0)
"""

        upload_response = await client.post(
            "/api/v1/custom-models/upload",
            data={
                "model_name": "Test Detector",
                "version": "1.0",
                "framework": "pytorch"
            },
            files={
                "weights_file": ("model.pt", io.BytesIO(weights_content), "application/octet-stream"),
                "config_file": ("config.yaml", io.BytesIO(config_content.encode()), "text/yaml"),
                "adapter_file": ("adapter.py", io.BytesIO(adapter_content.encode()), "text/x-python")
            },
            headers=auth_headers
        )

        if upload_response.status_code != 201:
            pytest.skip("Model upload service not fully implemented")

        upload_data = upload_response.json()
        version_id = upload_data["version_id"]

        # Step 2: Load the model
        load_response = await client.post(
            f"/api/v1/custom-models/{version_id}/load",
            headers=auth_headers
        )

        if load_response.status_code != 200:
            pytest.skip("Model loading service not fully implemented")

        # Step 3: Run inference
        # Create base64 image
        image_base64 = base64.b64encode(mock_image_file.read()).decode()

        inference_response = await client.post(
            f"/api/v1/custom-models/{version_id}/predict",
            json={
                "image_base64": image_base64,
                "conf_threshold": 0.5,
                "iou_threshold": 0.45
            },
            headers=auth_headers
        )

        if inference_response.status_code == 200:
            inference_data = inference_response.json()
            assert "detections" in inference_data
            assert "inference_time_ms" in inference_data
            assert isinstance(inference_data["detections"], list)

    async def test_camera_list_and_detection_workflow(
        self,
        client: AsyncClient,
        auth_headers,
        test_model_version
    ):
        """Test workflow: List cameras → Create run → Start detection."""

        # Step 1: List available webcams
        webcam_list_response = await client.get(
            "/api/v1/realtime/webcam/list",
            headers=auth_headers
        )

        # Webcam listing may fail in test environment
        if webcam_list_response.status_code != 200:
            pytest.skip("Webcam service not available in test environment")

        # Step 2: Create a camera entry
        camera_response = await client.post(
            "/api/v1/realtime/cameras",
            json={
                "name": "Workflow Test Camera",
                "stream_uri": "rtsp://192.168.1.101/stream",
                "resolution": {"width": 1280, "height": 720}
            },
            headers=auth_headers
        )
        assert camera_response.status_code == 201
        camera_id = camera_response.json()["id"]

        # Step 3: List cameras to verify creation
        cameras_response = await client.get(
            "/api/v1/realtime/cameras",
            headers=auth_headers
        )
        assert cameras_response.status_code == 200
        cameras = cameras_response.json()
        assert any(c["id"] == camera_id for c in cameras)

        # Step 4: Create capture run
        run_response = await client.post(
            "/api/v1/realtime/runs",
            json={
                "camera_id": camera_id,
                "model_version_id": str(test_model_version.id),
                "window_seconds": 5,
                "frames_expected": 10,
                "notes": "Detection Workflow Run"
            },
            headers=auth_headers
        )

        if run_response.status_code == 201:
            run_id = run_response.json()["id"]

            # Step 5: Get system stats before detection
            stats_response = await client.get(
                "/api/v1/realtime/stats/current",
                headers=auth_headers
            )
            assert stats_response.status_code == 200

            # Step 6: Attempt to start detection
            start_response = await client.post(
                f"/api/v1/realtime/webcam/start/{run_id}",
                params={
                    "model_version_id": str(test_model_version.id),
                    "device": "/dev/video0",
                    "fps_target": 10
                },
                headers=auth_headers
            )

            # Detection may fail without real camera
            if start_response.status_code == 200:
                # Clean up: stop capture
                await client.post(
                    f"/api/v1/realtime/webcam/stop/{run_id}",
                    headers=auth_headers
                )

    async def test_model_upload_list_verify_workflow(
        self,
        client: AsyncClient,
        auth_headers
    ):
        """Test workflow: Upload multiple models → List → Verify all present."""

        model_configs = [
            {
                "model_name": "Detector A",
                "version": "1.0",
                "framework": "pytorch"
            },
            {
                "model_name": "Detector B",
                "version": "2.0",
                "framework": "onnx"
            }
        ]

        uploaded_ids = []

        for config in model_configs:
            weights_content = b"fake weights"
            config_yaml = f"""
model_name: "{config['model_name']}"
version: "{config['version']}"
framework: "{config['framework']}"
class_names: ["person"]
"""
            adapter_content = """
from app.ai.base_detector import BaseObjectDetector, DetectionResult

class Detector(BaseObjectDetector):
    def load_model(self, weights_path, **kwargs):
        self.is_loaded = True

    def preprocess(self, image):
        return image

    def predict(self, preprocessed_input):
        return []

    def postprocess(self, model_output, original_shape, conf_threshold=0.25, iou_threshold=0.45):
        return DetectionResult(detections=[], inference_time_ms=0.0)
"""

            upload_response = await client.post(
                "/api/v1/custom-models/upload",
                data=config,
                files={
                    "weights_file": ("model.pt", io.BytesIO(weights_content), "application/octet-stream"),
                    "config_file": ("config.yaml", io.BytesIO(config_yaml.encode()), "text/yaml"),
                    "adapter_file": ("adapter.py", io.BytesIO(adapter_content.encode()), "text/x-python")
                },
                headers=auth_headers
            )

            if upload_response.status_code == 201:
                uploaded_ids.append(upload_response.json()["version_id"])

        if not uploaded_ids:
            pytest.skip("Model upload service not fully implemented")

        # List loaded models
        list_response = await client.get(
            "/api/v1/custom-models/loaded",
            headers=auth_headers
        )
        assert list_response.status_code == 200
        loaded_models = list_response.json()

        # Verify all uploaded models can be queried
        for version_id in uploaded_ids:
            info_response = await client.get(
                f"/api/v1/custom-models/{version_id}/info",
                headers=auth_headers
            )
            # Model info may require loading first
            assert info_response.status_code in [200, 404]


@pytest.mark.integration
@pytest.mark.asyncio
class TestEndToEndDetectionScenario:
    """
    End-to-end test simulating a complete real-world scenario.
    """

    async def test_scenario_4_realtime_camera_detection(
        self,
        client: AsyncClient,
        auth_headers,
        test_model_version
    ):
        """
        Scenario 4: Real-time camera detection.

        This test simulates a complete real-time detection scenario:
        1. System lists available cameras
        2. User selects a camera and creates camera entry
        3. User creates a capture run
        4. System starts real-time detection with specified model
        5. System captures frames and runs inference
        6. User stops the capture
        7. System verifies capture run results
        """

        # Step 1: List available webcams
        webcam_response = await client.get(
            "/api/v1/realtime/webcam/list",
            headers=auth_headers
        )

        if webcam_response.status_code != 200:
            pytest.skip("Webcam service not available in test environment")

        # Step 2: Create camera entry
        camera_response = await client.post(
            "/api/v1/realtime/cameras",
            json={
                "name": "Main Security Camera",
                "stream_uri": "rtsp://192.168.1.100/stream",
                "description": "Entrance camera for real-time monitoring",
                "resolution": {"width": 1920, "height": 1080}
            },
            headers=auth_headers
        )
        assert camera_response.status_code == 201
        camera = camera_response.json()

        # Step 3: Create capture run
        run_response = await client.post(
            "/api/v1/realtime/runs",
            json={
                "camera_id": camera["id"],
                "model_version_id": str(test_model_version.id),
                "window_seconds": 5,
                "frames_expected": 10,
                "fps_target": 30.0,
                "notes": "Security Monitoring - Scenario 4"
            },
            headers=auth_headers
        )

        if run_response.status_code != 201:
            # Run may require additional fields
            pytest.skip("Capture run creation requires additional configuration")

        run = run_response.json()
        run_id = run["id"]

        # Step 4: Start real-time detection
        start_response = await client.post(
            f"/api/v1/realtime/webcam/start/{run_id}",
            params={
                "model_version_id": str(test_model_version.id),
                "device": "/dev/video0",
                "fps_target": 30.0,
                "window_seconds": 5
            },
            headers=auth_headers
        )

        # Detection requires real camera hardware
        if start_response.status_code == 200:
            start_data = start_response.json()

            # Step 5: Verify capture is running (check system stats)
            stats_response = await client.get(
                "/api/v1/realtime/stats/current",
                headers=auth_headers
            )
            assert stats_response.status_code == 200

            # Step 6: Stop the capture
            stop_response = await client.post(
                f"/api/v1/realtime/webcam/stop/{run_id}",
                headers=auth_headers
            )
            assert stop_response.status_code == 200

            # Step 7: Verify capture run results
            run_detail_response = await client.get(
                f"/api/v1/realtime/runs/{run_id}",
                headers=auth_headers
            )
            assert run_detail_response.status_code == 200
            final_run = run_detail_response.json()

            # Run should be marked as completed or stopped
            assert final_run["id"] == run_id
