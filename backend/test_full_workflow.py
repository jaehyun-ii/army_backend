"""
Full workflow test: Dataset upload → Model upload → Patch generation → Patch application → Noise attacks
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.yolo_dataset_upload_service import yolo_dataset_upload_service
from app.services.patch_service import patch_service
from app.services.patch_attack_service import patch_attack_service
from app.services.noise_attack_service import noise_attack_service
from app import crud, schemas


async def test_full_workflow():
    """Test complete attack workflow."""

    # Create async engine
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(
        database_url,
        echo=False,
    )

    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        try:
            print("=" * 80)
            print("FULL WORKFLOW TEST: Dataset → Model → Patch → Attacks")
            print("=" * 80)

            # ============================================================
            # Step 1: Upload Dataset
            # ============================================================
            print("\n[Step 1] Uploading YOLO Dataset...")
            print("-" * 80)

            import random
            dataset_name = f"COCO_Person_100_Workflow_{random.randint(1000, 9999)}"

            dataset, images, upload_stats = await yolo_dataset_upload_service.upload_yolo_dataset(
                db=session,
                images_folder="/home/jaehyun/datasets/coco_person_100/images",
                labels_folder="/home/jaehyun/datasets/coco_person_100/labels",
                dataset_name=dataset_name,
                classes_file="/home/jaehyun/datasets/coco_person_100/classes.txt",
                description="COCO Person 100 dataset for workflow test",
                owner_id=None,
            )

            print(f"✓ Dataset uploaded: {dataset.id}")
            print(f"  - Name: {dataset.name}")
            print(f"  - Images: {len(images)}")
            print(f"  - Annotations: {upload_stats['total_annotations']}")
            print(f"  - Unmatched images: {upload_stats['unmatched_images']}")

            dataset_id = dataset.id

            # ============================================================
            # Step 2: Upload Model
            # ============================================================
            print("\n[Step 2] Uploading Model...")
            print("-" * 80)

            model_name = f"YOLOv8n_Workflow_{random.randint(1000, 9999)}"

            # Read config
            import yaml
            with open("/home/jaehyun/army/test_model/yolov8/config.yaml", "r") as f:
                config = yaml.safe_load(f)

            # Create labelmap from class_names
            labelmap = {str(i): name for i, name in enumerate(config["class_names"])}

            # Create model record
            model = await crud.od_model.create(
                session,
                obj_in=schemas.ODModelCreate(
                    name=model_name,
                    description="YOLOv8n model for workflow test",
                    framework=config["framework"],
                    version=config["model_version"],
                    input_spec={
                        "width": config["input_size"][0],
                        "height": config["input_size"][1],
                        "channels": 3,
                    },
                    labelmap=labelmap,
                    inference_params={
                        **config["inference_params"],
                        "estimator_type": "yolo",  # Required for estimator loader
                    },
                ),
                owner_id=None,
            )

            # Note: In production, artifacts would point to actual storage locations
            # For testing, we use the direct file paths in storage_key
            # Create artifact record
            artifact = await crud.model_artifact.create(
                session,
                obj_in=schemas.ODModelArtifactCreate(
                    model_id=model.id,
                    artifact_type="weights",
                    file_name=config["weights_file"],
                    storage_key="/home/jaehyun/army/test_model/yolov8/yolov8n.pt",
                    size_bytes=Path("/home/jaehyun/army/test_model/yolov8/yolov8n.pt").stat().st_size,
                ),
                owner_id=None,
            )

            # Create adapter artifact
            adapter_artifact = await crud.model_artifact.create(
                session,
                obj_in=schemas.ODModelArtifactCreate(
                    model_id=model.id,
                    artifact_type="support",
                    file_name="adapter.py",
                    storage_key="/home/jaehyun/army/test_model/yolov8/adapter.py",
                    size_bytes=Path("/home/jaehyun/army/test_model/yolov8/adapter.py").stat().st_size,
                ),
                owner_id=None,
            )

            await session.commit()

            # Refresh to load artifacts
            await session.refresh(model)

            print(f"✓ Model uploaded: {model.id}")
            print(f"  - Name: {model.name}")
            print(f"  - Framework: {model.framework}")
            print(f"  - Classes: {len(labelmap)}")
            print(f"  - Artifacts: {len(model.artifacts)}")

            model_id = model.id

            # ============================================================
            # Step 3: Generate Adversarial Patch
            # ============================================================
            print("\n[Step 3] Generating Adversarial Patch...")
            print("-" * 80)
            print("  (This may take a few minutes...)")

            patch_name = f"Person_Patch_Workflow_{random.randint(1000, 9999)}"

            patch_record = await patch_service.generate_patch(
                db=session,
                patch_name=patch_name,
                attack_method="robust_dpatch",
                source_dataset_id=dataset_id,
                model_id=model_id,
                target_class="person",
                patch_size=50,  # Smaller patch for faster testing
                learning_rate=5.0,
                iterations=10,  # Reduced for faster testing
                session_id=None,
                current_user_id=None,
            )

            print(f"✓ Patch generated: {patch_record.id}")
            print(f"  - Name: {patch_record.name}")
            print(f"  - Method: {patch_record.method}")
            print(f"  - Target class: {patch_record.target_class}")
            print(f"  - Storage: {patch_record.storage_key}")

            patch_id = patch_record.id

            # ============================================================
            # Step 4: Apply Patch to Dataset
            # ============================================================
            print("\n[Step 4] Applying Patch to Dataset...")
            print("-" * 80)

            patch_attack_name = f"Patch_Attack_Workflow_{random.randint(1000, 9999)}"

            attack_dataset_patch, output_dataset_id_patch = await patch_attack_service.apply_patch_to_dataset(
                db=session,
                attack_name=patch_attack_name,
                patch_id=patch_id,
                base_dataset_id=dataset_id,
                session_id=None,
                current_user_id=None,
            )

            print(f"✓ Patch applied to dataset")
            print(f"  - Attack dataset ID: {attack_dataset_patch.id}")
            print(f"  - Output dataset ID: {output_dataset_id_patch}")
            print(f"  - Processed images: {attack_dataset_patch.parameters.get('processed_images')}")
            print(f"  - Failed images: {attack_dataset_patch.parameters.get('failed_images')}")

            # ============================================================
            # Step 5: FGSM Noise Attack
            # ============================================================
            print("\n[Step 5] Running FGSM Noise Attack...")
            print("-" * 80)

            fgsm_attack_name = f"FGSM_Attack_Workflow_{random.randint(1000, 9999)}"

            attack_dataset_fgsm, output_dataset_id_fgsm = await noise_attack_service.create_noise_attack_dataset(
                db=session,
                attack_name=fgsm_attack_name,
                attack_method="fgsm",
                base_dataset_id=dataset_id,
                model_id=model_id,
                epsilon=8.0,
                alpha=None,
                iterations=None,
                session_id=None,
                current_user_id=None,
            )

            print(f"✓ FGSM attack completed")
            print(f"  - Attack dataset ID: {attack_dataset_fgsm.id}")
            print(f"  - Output dataset ID: {output_dataset_id_fgsm}")
            print(f"  - Processed images: {attack_dataset_fgsm.parameters.get('processed_images')}")
            print(f"  - Failed images: {attack_dataset_fgsm.parameters.get('failed_images')}")

            # ============================================================
            # Step 6: PGD Noise Attack
            # ============================================================
            print("\n[Step 6] Running PGD Noise Attack...")
            print("-" * 80)

            pgd_attack_name = f"PGD_Attack_Workflow_{random.randint(1000, 9999)}"

            attack_dataset_pgd, output_dataset_id_pgd = await noise_attack_service.create_noise_attack_dataset(
                db=session,
                attack_name=pgd_attack_name,
                attack_method="pgd",
                base_dataset_id=dataset_id,
                model_id=model_id,
                epsilon=8.0,
                alpha=2.0,
                iterations=10,
                session_id=None,
                current_user_id=None,
            )

            print(f"✓ PGD attack completed")
            print(f"  - Attack dataset ID: {attack_dataset_pgd.id}")
            print(f"  - Output dataset ID: {output_dataset_id_pgd}")
            print(f"  - Processed images: {attack_dataset_pgd.parameters.get('processed_images')}")
            print(f"  - Failed images: {attack_dataset_pgd.parameters.get('failed_images')}")

            # ============================================================
            # Summary
            # ============================================================
            print("\n" + "=" * 80)
            print("WORKFLOW TEST COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            print(f"\n✓ Dataset: {dataset_id}")
            print(f"✓ Model: {model_id}")
            print(f"✓ Patch: {patch_id}")
            print(f"✓ Patch Attack Dataset: {attack_dataset_patch.id}")
            print(f"✓ FGSM Attack Dataset: {attack_dataset_fgsm.id}")
            print(f"✓ PGD Attack Dataset: {attack_dataset_pgd.id}")

        except Exception as e:
            print(f"\n✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_full_workflow())
