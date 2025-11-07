"""
Full workflow test using HTTP API endpoints:
Dataset upload → Model upload → Patch generation → Patch application → Noise attacks
"""
import requests
import random
from pathlib import Path
import time

# Backend URL
BASE_URL = "http://localhost:8000/api/v1"


def test_full_workflow():
    """Test complete attack workflow via API endpoints."""

    try:
        print("=" * 80)
        print("FULL WORKFLOW TEST: Dataset → Model → Patch → Attacks (via API)")
        print("=" * 80)

        # ============================================================
        # Step 1: Upload Dataset
        # ============================================================
        print("\n[Step 1] Uploading YOLO Dataset...")
        print("-" * 80)

        dataset_name = f"COCO_Person_100_Workflow_{random.randint(1000, 9999)}"

        response = requests.post(
            f"{BASE_URL}/dataset-service/upload-yolo",
            json={
                'images_folder': '/home/jaehyun/datasets/coco_person_100/images',
                'labels_folder': '/home/jaehyun/datasets/coco_person_100/labels',
                'dataset_name': dataset_name,
                'classes_file': '/home/jaehyun/datasets/coco_person_100/classes.txt',
                'description': 'COCO Person 100 dataset for workflow test',
            },
            timeout=120
        )

        if response.status_code != 201:
            print(f"✗ Dataset upload failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return

        dataset_data = response.json()
        dataset_id = dataset_data["dataset"]["id"]

        print(f"✓ Dataset uploaded: {dataset_id}")
        print(f"  - Name: {dataset_data['dataset']['name']}")
        print(f"  - Images: {dataset_data.get('image_count', len(dataset_data.get('images', [])))}")
        print(f"  - Annotations: {dataset_data.get('upload_stats', {}).get('total_annotations', 0)}")

        # ============================================================
        # Step 2: Upload Model
        # ============================================================
        print("\n[Step 2] Uploading Model...")
        print("-" * 80)

        model_name = f"YOLOv8n_Workflow_{random.randint(1000, 9999)}"

        # Upload model files
        with open("/home/jaehyun/army/test_model/yolov8/yolov8n.pt", "rb") as weights_f, \
             open("/home/jaehyun/army/test_model/yolov8/config.yaml", "rb") as yaml_f:

            files = {
                'weights_file': ('yolov8n.pt', weights_f, 'application/octet-stream'),
                'yaml_file': ('config.yaml', yaml_f, 'application/x-yaml'),
            }

            data = {
                'name': model_name,
                'description': 'YOLOv8n model for workflow test',
            }

            response = requests.post(
                f"{BASE_URL}/models/upload",
                files=files,
                data=data,
                timeout=120
            )

        if response.status_code != 201:
            print(f"✗ Model upload failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return

        model_data = response.json()
        model_id = model_data["id"]

        print(f"✓ Model uploaded: {model_id}")
        print(f"  - Name: {model_data['name']}")
        print(f"  - Framework: {model_data['framework']}")

        # ============================================================
        # Step 3: Generate Adversarial Patch
        # ============================================================
        print("\n[Step 3] Generating Adversarial Patch...")
        print("-" * 80)
        print("  (This may take a few minutes...)")

        patch_name = f"Person_Patch_Workflow_{random.randint(1000, 9999)}"

        patch_data = {
            "patch_name": patch_name,
            "attack_method": "robust_dpatch",
            "source_dataset_id": dataset_id,
            "model_id": model_id,
            "target_class": "person",
            "patch_size": 50,  # Smaller patch for faster testing
            "learning_rate": 5.0,
            "iterations": 50,  # Minimum required
        }

        response = requests.post(
            f"{BASE_URL}/patches/generate",
            json=patch_data,
            timeout=600  # 10 minutes timeout for patch generation
        )

        if response.status_code != 201:
            print(f"✗ Patch generation failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return

        patch_result = response.json()
        patch_id = patch_result["patch"]["id"]

        print(f"✓ Patch generated: {patch_id}")
        print(f"  - Name: {patch_result['patch']['name']}")
        print(f"  - Method: {patch_result['patch']['method']}")
        print(f"  - Target class: {patch_result['patch']['target_class']}")
        print(f"  - Storage: {patch_result['patch']['storage_key']}")

        # ============================================================
        # Step 4: Apply Patch to Dataset
        # ============================================================
        print("\n[Step 4] Applying Patch to Dataset...")
        print("-" * 80)

        patch_attack_name = f"Patch_Attack_Workflow_{random.randint(1000, 9999)}"

        patch_attack_data = {
            "attack_name": patch_attack_name,
            "patch_id": patch_id,
            "base_dataset_id": dataset_id,
        }

        response = requests.post(
            f"{BASE_URL}/attack-datasets/patch",
            json=patch_attack_data,
            timeout=300  # 5 minutes timeout
        )

        if response.status_code != 201:
            print(f"✗ Patch application failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return

        patch_attack_result = response.json()

        print(f"✓ Patch applied to dataset")
        print(f"  - Attack dataset ID: {patch_attack_result['attack_dataset']['id']}")
        print(f"  - Output dataset ID: {patch_attack_result['output_dataset_id']}")
        print(f"  - Processed images: {patch_attack_result['statistics']['processed_images']}")
        print(f"  - Failed images: {patch_attack_result['statistics']['failed_images']}")

        # ============================================================
        # Step 5: FGSM Noise Attack
        # ============================================================
        print("\n[Step 5] Running FGSM Noise Attack...")
        print("-" * 80)

        fgsm_attack_name = f"FGSM_Attack_Workflow_{random.randint(1000, 9999)}"

        fgsm_data = {
            "attack_name": fgsm_attack_name,
            "attack_method": "fgsm",
            "base_dataset_id": dataset_id,
            "model_id": model_id,
            "epsilon": 8.0,
        }

        response = requests.post(
            f"{BASE_URL}/attack-datasets/noise",
            json=fgsm_data,
            timeout=300  # 5 minutes timeout
        )

        if response.status_code != 201:
            print(f"✗ FGSM attack failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return

        fgsm_result = response.json()

        print(f"✓ FGSM attack completed")
        print(f"  - Attack dataset ID: {fgsm_result['attack_dataset']['id']}")
        print(f"  - Output dataset ID: {fgsm_result['output_dataset_id']}")
        print(f"  - Processed images: {fgsm_result['statistics']['processed_images']}")
        print(f"  - Failed images: {fgsm_result['statistics']['failed_images']}")

        # ============================================================
        # Step 6: PGD Noise Attack
        # ============================================================
        print("\n[Step 6] Running PGD Noise Attack...")
        print("-" * 80)

        pgd_attack_name = f"PGD_Attack_Workflow_{random.randint(1000, 9999)}"

        pgd_data = {
            "attack_name": pgd_attack_name,
            "attack_method": "pgd",
            "base_dataset_id": dataset_id,
            "model_id": model_id,
            "epsilon": 8.0,
            "alpha": 2.0,
            "iterations": 10,
        }

        response = requests.post(
            f"{BASE_URL}/attack-datasets/noise",
            json=pgd_data,
            timeout=300  # 5 minutes timeout
        )

        if response.status_code != 201:
            print(f"✗ PGD attack failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return

        pgd_result = response.json()

        print(f"✓ PGD attack completed")
        print(f"  - Attack dataset ID: {pgd_result['attack_dataset']['id']}")
        print(f"  - Output dataset ID: {pgd_result['output_dataset_id']}")
        print(f"  - Processed images: {pgd_result['statistics']['processed_images']}")
        print(f"  - Failed images: {pgd_result['statistics']['failed_images']}")

        # ============================================================
        # Summary
        # ============================================================
        print("\n" + "=" * 80)
        print("WORKFLOW TEST COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print(f"\n✓ Dataset: {dataset_id}")
        print(f"✓ Model: {model_id}")
        print(f"✓ Patch: {patch_id}")
        print(f"✓ Patch Attack Dataset: {patch_attack_result['attack_dataset']['id']}")
        print(f"✓ FGSM Attack Dataset: {fgsm_result['attack_dataset']['id']}")
        print(f"✓ PGD Attack Dataset: {pgd_result['attack_dataset']['id']}")

    except requests.exceptions.RequestException as e:
        print(f"\n✗ API request failed: {e}")
        raise
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    test_full_workflow()
