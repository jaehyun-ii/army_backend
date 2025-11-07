"""
Simple test for noise attacks only (FGSM and PGD)
"""
import requests
import random

BASE_URL = "http://localhost:8000/api/v1"


def test_noise_attacks():
    """Test noise attacks without patch generation."""

    try:
        print("=" * 80)
        print("NOISE ATTACK TEST: Dataset → Model → FGSM → PGD")
        print("=" * 80)

        # Step 1: Upload Dataset
        print("\n[Step 1] Uploading YOLO Dataset...")
        print("-" * 80)

        dataset_name = f"COCO_Person_100_Noise_{random.randint(1000, 9999)}"

        response = requests.post(
            f"{BASE_URL}/dataset-service/upload-yolo",
            json={
                'images_folder': '/home/jaehyun/datasets/coco_person_100/images',
                'labels_folder': '/home/jaehyun/datasets/coco_person_100/labels',
                'dataset_name': dataset_name,
                'description': 'COCO Person 100 dataset for noise test',
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

        # Step 2: Upload Model
        print("\n[Step 2] Uploading Model...")
        print("-" * 80)

        model_name = f"YOLOv8n_Noise_{random.randint(1000, 9999)}"

        with open("/home/jaehyun/army/test_model/yolov8/yolov8n.pt", "rb") as weights_f, \
             open("/home/jaehyun/army/test_model/yolov8/config.yaml", "rb") as yaml_f:

            files = {
                'weights_file': ('yolov8n.pt', weights_f, 'application/octet-stream'),
                'yaml_file': ('config.yaml', yaml_f, 'application/x-yaml'),
            }

            data = {
                'name': model_name,
                'description': 'YOLOv8n model for noise test',
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

        # Step 3: FGSM Attack
        print("\n[Step 3] Running FGSM Attack...")
        print("-" * 80)

        fgsm_attack_name = f"FGSM_Noise_{random.randint(1000, 9999)}"

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
            timeout=300
        )

        if response.status_code != 201:
            print(f"✗ FGSM attack failed: {response.status_code}")
            print(f"  Response: {response.text}")
            print("\n  Skipping to PGD test...")
        else:
            fgsm_result = response.json()
            print(f"✓ FGSM attack completed")
            print(f"  - Attack dataset ID: {fgsm_result['attack_dataset']['id']}")
            print(f"  - Output dataset ID: {fgsm_result['output_dataset_id']}")
            print(f"  - Processed: {fgsm_result['statistics']['processed_images']}")
            print(f"  - Failed: {fgsm_result['statistics']['failed_images']}")

        # Step 4: PGD Attack
        print("\n[Step 4] Running PGD Attack...")
        print("-" * 80)

        pgd_attack_name = f"PGD_Noise_{random.randint(1000, 9999)}"

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
            timeout=300
        )

        if response.status_code != 201:
            print(f"✗ PGD attack failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return

        pgd_result = response.json()

        print(f"✓ PGD attack completed")
        print(f"  - Attack dataset ID: {pgd_result['attack_dataset']['id']}")
        print(f"  - Output dataset ID: {pgd_result['output_dataset_id']}")
        print(f"  - Processed: {pgd_result['statistics']['processed_images']}")
        print(f"  - Failed: {pgd_result['statistics']['failed_images']}")

        # Summary
        print("\n" + "=" * 80)
        print("NOISE ATTACK TEST COMPLETED!")
        print("=" * 80)
        print(f"\n✓ Dataset: {dataset_id}")
        print(f"✓ Model: {model_id}")

    except requests.exceptions.RequestException as e:
        print(f"\n✗ API request failed: {e}")
        raise
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    test_noise_attacks()
