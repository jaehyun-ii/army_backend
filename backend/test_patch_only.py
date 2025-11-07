"""
Comprehensive test for all patch attack methods.

Tests all supported patch generation methods:
- patch: AdversarialPatchPyTorch (general patch with transformations)
- dpatch: DPatch (object detector specific)
- robust_dpatch: RobustDPatch (robust to cropping, rotation, brightness)

Based on:
- test_noise_only.py
- yolov8_adversarial_patch_tank.ipynb
"""
import requests
import random
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api/v1"

# Test configuration for all patch methods
PATCH_METHODS = [
    {
        "attack_method": "patch",
        "description": "AdversarialPatchPyTorch (general patch with transformations)",
        "patch_size": 200,
        "learning_rate": 5.0,
        "iterations": 50,
    },
    {
        "attack_method": "dpatch",
        "description": "DPatch (object detector specific)",
        "patch_size": 150,
        "learning_rate": 5.0,
        "iterations": 50,
    },
    {
        "attack_method": "robust_dpatch",
        "description": "RobustDPatch (robust to transformations)",
        "patch_size": 150,
        "learning_rate": 5.0,
        "iterations": 50,
    },
]


def test_single_patch_method(
    dataset_id: str,
    model_id: str,
    method_config: Dict[str, Any],
    test_number: int,
    total_tests: int,
) -> Dict[str, Any]:
    """Test a single patch generation method."""

    attack_method = method_config["attack_method"]
    description = method_config["description"]

    print("\n" + "=" * 80)
    print(f"TEST [{test_number}/{total_tests}]: {attack_method.upper()}")
    print(f"Description: {description}")
    print("=" * 80)

    try:
        # Step 1: Generate Patch
        print(f"\n[Step 1] Generating {attack_method.upper()} Patch...")
        print("-" * 80)
        print(f"Parameters:")
        print(f"  - Patch size: {method_config['patch_size']}x{method_config['patch_size']}")
        print(f"  - Learning rate: {method_config['learning_rate']}")
        print(f"  - Iterations: {method_config['iterations']}")
        print("This may take several minutes...")

        patch_name = f"Person_{attack_method}_{random.randint(1000, 9999)}"

        patch_data = {
            "patch_name": patch_name,
            "attack_method": attack_method,
            "source_dataset_id": dataset_id,
            "model_id": model_id,
            "target_class": "person",
            "patch_size": method_config["patch_size"],
            "learning_rate": method_config["learning_rate"],
            "iterations": method_config["iterations"],
        }

        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/patches/generate",
            json=patch_data,
            timeout=1800  # 30 minutes timeout
        )
        elapsed_time = time.time() - start_time

        if response.status_code != 201:
            print(f"✗ Patch generation failed: {response.status_code}")
            print(f"  Response: {response.text}")
            print(f"  Elapsed time: {elapsed_time:.1f}s")
            return {
                "method": attack_method,
                "success": False,
                "error": response.text,
                "elapsed_time": elapsed_time,
            }

        patch_result = response.json()
        patch_id = patch_result["patch"]["id"]

        print(f"✓ Patch generated: {patch_id}")
        print(f"  - Elapsed time: {elapsed_time:.1f}s")
        print(f"  - Patch file: {patch_result.get('patch_file_path', 'N/A')}")

        # Step 2: Apply Patch to Dataset
        print(f"\n[Step 2] Applying {attack_method.upper()} Patch to Dataset...")
        print("-" * 80)

        attack_name = f"Patched_{attack_method}_{random.randint(1000, 9999)}"

        apply_data = {
            "attack_name": attack_name,
            "patch_id": patch_id,
            "base_dataset_id": dataset_id,
        }

        response = requests.post(
            f"{BASE_URL}/attack-datasets/patch",
            json=apply_data,
            timeout=300
        )

        if response.status_code != 201:
            print(f"✗ Patch application failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return {
                "method": attack_method,
                "success": False,
                "patch_id": patch_id,
                "error": f"Application failed: {response.text}",
                "elapsed_time": elapsed_time,
            }

        attack_result = response.json()

        print(f"✓ Patch applied to dataset")
        print(f"  - Attack dataset ID: {attack_result['attack_dataset']['id']}")
        print(f"  - Output dataset ID: {attack_result['output_dataset_id']}")
        print(f"  - Processed: {attack_result['statistics']['processed_images']}")
        print(f"  - Failed: {attack_result['statistics']['failed_images']}")

        print(f"\n✓ {attack_method.upper()} test completed successfully!")

        return {
            "method": attack_method,
            "success": True,
            "patch_id": patch_id,
            "attack_dataset_id": attack_result['attack_dataset']['id'],
            "output_dataset_id": attack_result['output_dataset_id'],
            "processed_images": attack_result['statistics']['processed_images'],
            "failed_images": attack_result['statistics']['failed_images'],
            "elapsed_time": elapsed_time,
        }

    except requests.exceptions.Timeout as e:
        print(f"\n✗ Request timeout: {e}")
        print("  Patch generation can take a long time. Consider reducing iterations.")
        return {
            "method": attack_method,
            "success": False,
            "error": f"Timeout: {str(e)}",
        }
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "method": attack_method,
            "success": False,
            "error": str(e),
        }


def test_all_patch_methods():
    """Test all patch attack methods comprehensively."""

    print("=" * 80)
    print("COMPREHENSIVE PATCH ATTACK TEST")
    print("Testing all patch generation methods")
    print("=" * 80)

    try:
        # Step 1: Upload Dataset (shared for all tests)
        print("\n[SETUP] Uploading YOLO Dataset...")
        print("-" * 80)

        dataset_name = f"COCO_Person_100_AllPatches_{random.randint(1000, 9999)}"

        response = requests.post(
            f"{BASE_URL}/dataset-service/upload-yolo",
            json={
                'images_folder': '/home/jaehyun/datasets/coco_person_100/images',
                'labels_folder': '/home/jaehyun/datasets/coco_person_100/labels',
                'dataset_name': dataset_name,
                'description': 'COCO Person 100 dataset for testing all patch methods',
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

        # Step 2: Upload Model (shared for all tests)
        print("\n[SETUP] Uploading Model...")
        print("-" * 80)

        model_name = f"YOLOv8n_AllPatches_{random.randint(1000, 9999)}"

        with open("/home/jaehyun/army/test_model/yolov8/yolov8n.pt", "rb") as weights_f, \
             open("/home/jaehyun/army/test_model/yolov8/config.yaml", "rb") as yaml_f:

            files = {
                'weights_file': ('yolov8n.pt', weights_f, 'application/octet-stream'),
                'yaml_file': ('config.yaml', yaml_f, 'application/x-yaml'),
            }

            data = {
                'name': model_name,
                'description': 'YOLOv8n model for testing all patch methods',
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

        # Step 3: Test each patch method
        print("\n" + "=" * 80)
        print("TESTING ALL PATCH METHODS")
        print("=" * 80)

        results = []
        total_tests = len(PATCH_METHODS)

        for i, method_config in enumerate(PATCH_METHODS, 1):
            result = test_single_patch_method(
                dataset_id=dataset_id,
                model_id=model_id,
                method_config=method_config,
                test_number=i,
                total_tests=total_tests,
            )
            results.append(result)

            # Brief pause between tests
            if i < total_tests:
                print("\n" + "-" * 80)
                print("Pausing 2 seconds before next test...")
                time.sleep(2)

        # Final Summary
        print("\n\n" + "=" * 80)
        print("COMPREHENSIVE TEST RESULTS")
        print("=" * 80)

        print(f"\n✓ Dataset: {dataset_id}")
        print(f"✓ Model: {model_id}")
        print(f"\nPatch Method Results:")
        print("-" * 80)

        success_count = 0
        for result in results:
            method = result["method"]
            success = result["success"]
            status_symbol = "✓" if success else "✗"

            print(f"\n{status_symbol} {method.upper()}")
            if success:
                success_count += 1
                print(f"  - Patch ID: {result['patch_id']}")
                print(f"  - Attack Dataset ID: {result['attack_dataset_id']}")
                print(f"  - Output Dataset ID: {result['output_dataset_id']}")
                print(f"  - Processed images: {result['processed_images']}")
                print(f"  - Failed images: {result['failed_images']}")
                print(f"  - Elapsed time: {result['elapsed_time']:.1f}s")
            else:
                print(f"  - Error: {result.get('error', 'Unknown error')}")
                if 'elapsed_time' in result:
                    print(f"  - Elapsed time: {result['elapsed_time']:.1f}s")

        print("\n" + "=" * 80)
        print(f"OVERALL: {success_count}/{total_tests} tests passed")
        print("=" * 80)

        if success_count == total_tests:
            print("\n✓ All patch methods tested successfully!")
        else:
            print(f"\n⚠ {total_tests - success_count} test(s) failed")

        print("\n" + "=" * 80)
        print("NEXT STEPS:")
        print("=" * 80)
        print("1. Compare detection results on original vs patched images")
        print("2. Evaluate attack success rate for each method")
        print("3. Compare effectiveness of different patch methods")
        print("4. Visualize patched images with detection boxes")
        print("=" * 80)

    except requests.exceptions.RequestException as e:
        print(f"\n✗ API request failed: {e}")
        raise
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    test_all_patch_methods()
