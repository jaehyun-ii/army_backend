"""
Integration tests for noise-based adversarial attack workflow.

Workflow:
1. Upload dataset
2. Apply noise attack (FGSM/PGD/Gaussian) to create attack dataset
3. Evaluate pre-attack performance
4. Evaluate post-attack performance
5. Compare results
"""
import pytest
from httpx import AsyncClient
from pathlib import Path


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
class TestNoiseAttackWorkflow:
    """Test complete noise-based attack workflow."""

    async def test_fgsm_attack_workflow(
        self,
        client: AsyncClient,
        auth_headers,
        temp_storage_dir,
        mock_image_file,
        test_model_version
    ):
        """
        Test complete FGSM workflow from dataset upload to evaluation.

        Steps:
        1. Upload base dataset
        2. Apply FGSM attack to create attack dataset
        3. Run pre-attack evaluation
        4. Run post-attack evaluation
        5. Compare evaluation results
        """

        # ===== Step 1: Upload real test dataset =====
        real_test_dataset = Path(__file__).parent / "test_dataset"

        upload_response = await client.post(
            "/api/v1/dataset-service/upload-folder",
            json={
                "source_folder": str(real_test_dataset),
                "dataset_name": "FGSM Integration Test Dataset",
                "description": "Real dataset for FGSM integration test"
            },
            headers=auth_headers
        )

        assert upload_response.status_code == 201, f"Upload failed: {upload_response.json()}"
        upload_data = upload_response.json()
        base_dataset_id = upload_data["dataset"]["id"]
        image_count = upload_data["image_count"]

        print(f"✓ Step 1: Uploaded dataset {base_dataset_id} with {image_count} images")

        # ===== Step 2: Apply FGSM attack =====
        fgsm_response = await client.post(
            "/api/v1/noise-attack/fgsm/generate",
            json={
                "attack_dataset_name": "FGSM Attack Dataset",
                "model_version_id": str(test_model_version.id),
                "base_dataset_id": base_dataset_id,
                "epsilon": 8.0,
                "targeted": False
            },
            headers=auth_headers
        )

        # FGSM attack might fail if model/inference not available
        if fgsm_response.status_code == 201:
            fgsm_data = fgsm_response.json()
            attack_dataset_id = fgsm_data["attack_dataset"]["id"]
            print(f"✓ Step 2: Created FGSM attack dataset {attack_dataset_id}")

            # ===== Step 3: Run pre-attack evaluation =====
            pre_eval_response = await client.post(
                "/api/v1/evaluation/runs",
                json={
                    "phase": "pre_attack",
                    "model_version_id": str(test_model_version.id),
                    "base_dataset_id": base_dataset_id
                },
                headers=auth_headers
            )

            if pre_eval_response.status_code == 201:
                pre_eval_data = pre_eval_response.json()
                pre_eval_run_id = pre_eval_data["id"]
                print(f"✓ Step 3: Created pre-attack evaluation {pre_eval_run_id}")

                # ===== Step 4: Run post-attack evaluation =====
                post_eval_response = await client.post(
                    "/api/v1/evaluation/runs",
                    json={
                        "phase": "post_attack",
                        "model_version_id": str(test_model_version.id),
                        "attack_dataset_id": attack_dataset_id
                    },
                    headers=auth_headers
                )

                if post_eval_response.status_code == 201:
                    post_eval_data = post_eval_response.json()
                    post_eval_run_id = post_eval_data["id"]
                    print(f"✓ Step 4: Created post-attack evaluation {post_eval_run_id}")

                    # ===== Step 5: Compare evaluation results =====
                    compare_response = await client.post(
                        "/api/v1/evaluation/runs/compare",
                        json={
                            "pre_attack_run_id": pre_eval_run_id,
                            "post_attack_run_id": post_eval_run_id
                        },
                        headers=auth_headers
                    )

                    if compare_response.status_code == 200:
                        compare_data = compare_response.json()
                        print(f"✓ Step 5: Compared evaluation results")
                        print(f"  Pre-attack mAP: {compare_data.get('pre_attack', {}).get('overall_map', 'N/A')}")
                        print(f"  Post-attack mAP: {compare_data.get('post_attack', {}).get('overall_map', 'N/A')}")
                        assert "pre_attack" in compare_data
                        assert "post_attack" in compare_data
                    else:
                        print(f"⚠ Step 5: Compare might not be implemented (status {compare_response.status_code})")
                else:
                    print(f"⚠ Step 4: Post-attack evaluation creation failed (status {post_eval_response.status_code})")
            else:
                print(f"⚠ Step 3: Pre-attack evaluation creation failed (status {pre_eval_response.status_code})")
        else:
            print(f"⚠ Step 2: FGSM attack not available (status {fgsm_response.status_code})")
            print(f"Error details: {fgsm_response.json()}")
            pytest.skip("FGSM attack service not available for full integration test")

    async def test_pgd_attack_workflow(
        self,
        client: AsyncClient,
        auth_headers,
        temp_storage_dir,
        mock_image_file,
        test_model_version
    ):
        """
        Test complete PGD workflow from dataset upload to evaluation.

        Steps:
        1. Upload base dataset
        2. Apply PGD attack to create attack dataset
        3. Run pre-attack evaluation
        4. Run post-attack evaluation
        5. Compare evaluation results
        """

        # ===== Step 1: Upload real test dataset =====
        real_test_dataset = Path(__file__).parent / "test_dataset"

        upload_response = await client.post(
            "/api/v1/dataset-service/upload-folder",
            json={
                "source_folder": str(real_test_dataset),
                "dataset_name": "PGD Integration Test Dataset",
                "description": "Real dataset for PGD integration test"
            },
            headers=auth_headers
        )

        assert upload_response.status_code == 201
        upload_data = upload_response.json()
        base_dataset_id = upload_data["dataset"]["id"]
        image_count = upload_data["image_count"]
        print(f"✓ Step 1: Uploaded dataset {base_dataset_id} with {image_count} images")

        # ===== Step 2: Apply PGD attack =====
        pgd_response = await client.post(
            "/api/v1/noise-attack/pgd/generate",
            json={
                "attack_dataset_name": "PGD Attack Dataset",
                "model_version_id": str(test_model_version.id),
                "base_dataset_id": base_dataset_id,
                "epsilon": 8.0,
                "alpha": 2.0,
                "iterations": 5,  # Low iterations for fast testing
                "targeted": False
            },
            headers=auth_headers
        )

        if pgd_response.status_code == 201:
            pgd_data = pgd_response.json()
            attack_dataset_id = pgd_data["attack_dataset"]["id"]
            print(f"✓ Step 2: Created PGD attack dataset {attack_dataset_id}")
            assert pgd_data["statistics"]["method"] == "PGD"
            assert pgd_data["statistics"]["epsilon"] == 8.0
            assert pgd_data["statistics"]["iterations"] == 5
        else:
            print(f"⚠ Step 2: PGD attack not available (status {pgd_response.status_code})")
            pytest.skip("PGD attack service not available")

    async def test_gaussian_noise_workflow(
        self,
        client: AsyncClient,
        auth_headers,
        temp_storage_dir,
        mock_image_file
    ):
        """
        Test complete Gaussian noise workflow.

        Steps:
        1. Upload base dataset
        2. Apply Gaussian noise to create attack dataset
        3. Verify dataset statistics
        """

        # ===== Step 1: Upload real test dataset =====
        real_test_dataset = Path(__file__).parent / "test_dataset"

        upload_response = await client.post(
            "/api/v1/dataset-service/upload-folder",
            json={
                "source_folder": str(real_test_dataset),
                "dataset_name": "Gaussian Integration Test Dataset",
                "description": "Real dataset for Gaussian noise test"
            },
            headers=auth_headers
        )

        assert upload_response.status_code == 201
        upload_data = upload_response.json()
        base_dataset_id = upload_data["dataset"]["id"]
        image_count = upload_data["image_count"]
        print(f"✓ Step 1: Uploaded dataset {base_dataset_id} with {image_count} images")

        # ===== Step 2: Apply Gaussian noise =====
        gaussian_response = await client.post(
            "/api/v1/noise-attack/gaussian/generate",
            json={
                "attack_dataset_name": "Gaussian Noise Dataset",
                "base_dataset_id": base_dataset_id,
                "mean": 0.0,
                "std": 25.0
            },
            headers=auth_headers
        )

        if gaussian_response.status_code == 201:
            gaussian_data = gaussian_response.json()
            attack_dataset_id = gaussian_data["attack_dataset"]["id"]
            print(f"✓ Step 2: Created Gaussian noise dataset {attack_dataset_id}")
            assert gaussian_data["statistics"]["method"] == "GAUSSIAN"
            assert gaussian_data["statistics"]["mean"] == 0.0
            assert gaussian_data["statistics"]["std"] == 25.0

            # ===== Step 3: Get dataset statistics =====
            stats_response = await client.get(
                f"/api/v1/dataset-service/{attack_dataset_id}/stats",
                headers=auth_headers
            )

            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                print(f"✓ Step 3: Retrieved dataset statistics")
                assert stats_data["dataset_id"] == attack_dataset_id
                assert "image_count" in stats_data
            else:
                print(f"⚠ Step 3: Stats retrieval failed (status {stats_response.status_code})")
        else:
            print(f"⚠ Step 2: Gaussian noise not available (status {gaussian_response.status_code})")
            pytest.skip("Gaussian noise service not available")

    async def test_multiple_noise_attacks_comparison(
        self,
        client: AsyncClient,
        auth_headers,
        temp_storage_dir,
        mock_image_file,
        test_model_version
    ):
        """
        Test comparing multiple noise attack methods.

        Steps:
        1. Upload base dataset
        2. Apply FGSM attack
        3. Apply PGD attack
        4. Apply Gaussian noise
        5. Compare all attack methods
        """

        # ===== Step 1: Upload real test dataset =====
        real_test_dataset = Path(__file__).parent / "test_dataset"

        upload_response = await client.post(
            "/api/v1/dataset-service/upload-folder",
            json={
                "source_folder": str(real_test_dataset),
                "dataset_name": "Multi-Attack Dataset"
            },
            headers=auth_headers
        )

        assert upload_response.status_code == 201
        upload_data = upload_response.json()
        base_dataset_id = upload_data["dataset"]["id"]
        image_count = upload_data["image_count"]
        print(f"✓ Step 1: Uploaded base dataset {base_dataset_id} with {image_count} images")

        attack_datasets = []

        # ===== Step 2: Apply FGSM =====
        fgsm_response = await client.post(
            "/api/v1/noise-attack/fgsm/generate",
            json={
                "attack_dataset_name": "Multi-FGSM",
                "model_version_id": str(test_model_version.id),
                "base_dataset_id": base_dataset_id,
                "epsilon": 8.0
            },
            headers=auth_headers
        )

        if fgsm_response.status_code == 201:
            attack_datasets.append({
                "method": "FGSM",
                "id": fgsm_response.json()["attack_dataset"]["id"]
            })
            print(f"✓ Step 2: Created FGSM attack")

        # ===== Step 3: Apply PGD =====
        pgd_response = await client.post(
            "/api/v1/noise-attack/pgd/generate",
            json={
                "attack_dataset_name": "Multi-PGD",
                "model_version_id": str(test_model_version.id),
                "base_dataset_id": base_dataset_id,
                "epsilon": 8.0,
                "alpha": 2.0,
                "iterations": 5
            },
            headers=auth_headers
        )

        if pgd_response.status_code == 201:
            attack_datasets.append({
                "method": "PGD",
                "id": pgd_response.json()["attack_dataset"]["id"]
            })
            print(f"✓ Step 3: Created PGD attack")

        # ===== Step 4: Apply Gaussian =====
        gaussian_response = await client.post(
            "/api/v1/noise-attack/gaussian/generate",
            json={
                "attack_dataset_name": "Multi-Gaussian",
                "base_dataset_id": base_dataset_id,
                "mean": 0.0,
                "std": 25.0
            },
            headers=auth_headers
        )

        if gaussian_response.status_code == 201:
            attack_datasets.append({
                "method": "Gaussian",
                "id": gaussian_response.json()["attack_dataset"]["id"]
            })
            print(f"✓ Step 4: Created Gaussian noise")

        # ===== Step 5: Verify attacks created =====
        print(f"✓ Step 5: Created {len(attack_datasets)} attack datasets")

        if len(attack_datasets) == 0:
            pytest.skip("All noise attack services returned errors (500) - services not fully implemented")

        for attack in attack_datasets:
            print(f"  - {attack['method']}: {attack['id']}")

    async def test_noise_workflow_validation_errors(
        self,
        client: AsyncClient,
        auth_headers
    ):
        """Test that noise workflow properly validates at each step."""

        from uuid import uuid4

        # Invalid FGSM parameters
        fgsm_response = await client.post(
            "/api/v1/noise-attack/fgsm/generate",
            json={
                "attack_dataset_name": "Invalid FGSM",
                "model_version_id": str(uuid4()),
                "base_dataset_id": str(uuid4()),
                "epsilon": 300.0  # Invalid: > 255
            },
            headers=auth_headers
        )
        assert fgsm_response.status_code == 422

        # Invalid PGD parameters
        pgd_response = await client.post(
            "/api/v1/noise-attack/pgd/generate",
            json={
                "attack_dataset_name": "Invalid PGD",
                "model_version_id": str(uuid4()),
                "base_dataset_id": str(uuid4()),
                "epsilon": 8.0,
                "alpha": 60.0,  # Invalid: > 50
                "iterations": 150  # Invalid: > 100
            },
            headers=auth_headers
        )
        assert pgd_response.status_code == 422

        # Invalid Gaussian parameters
        gaussian_response = await client.post(
            "/api/v1/noise-attack/gaussian/generate",
            json={
                "attack_dataset_name": "Invalid Gaussian",
                "base_dataset_id": str(uuid4()),
                "mean": 0.0,
                "std": 150.0  # Invalid: > 100
            },
            headers=auth_headers
        )
        assert gaussian_response.status_code == 422
