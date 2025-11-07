"""
Check if dataset and model are properly loaded
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app import crud


async def check_data(dataset_id: str, model_id: str):
    """Check dataset and model."""

    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Check dataset
            print(f"Checking dataset {dataset_id}...")
            dataset = await crud.dataset_2d.get(session, id=dataset_id)
            if not dataset:
                print(f"✗ Dataset not found")
                return

            print(f"✓ Dataset found: {dataset.name}")
            print(f"  Storage path: {dataset.storage_path}")

            # Check images
            images = await crud.image_2d.get_by_dataset(session, dataset_id=dataset_id)
            print(f"  Images in DB: {len(images)}")

            if images:
                img = images[0]
                print(f"  First image: {img.file_name}")
                print(f"  Storage key: {img.storage_key}")

                # Check file exists
                img_path = Path(settings.STORAGE_ROOT) / img.storage_key
                print(f"  Full path: {img_path}")
                print(f"  Exists: {img_path.exists()}")

            # Check model
            print(f"\nChecking model {model_id}...")
            model = await crud.od_model.get(session, id=model_id)
            if not model:
                print(f"✗ Model not found")
                return

            print(f"✓ Model found: {model.name}")
            print(f"  Framework: {model.framework}")
            print(f"  Labelmap: {model.labelmap}")
            print(f"  Artifacts: {len(model.artifacts)}")

            for artifact in model.artifacts:
                print(f"    - {artifact.artifact_type}: {artifact.storage_key}")
                print(f"      File name: {artifact.file_name}")
                if artifact.artifact_type == "weights":
                    weights_path_key = Path(artifact.storage_key)
                    print(f"      Storage key path exists: {weights_path_key.exists()}")
                    weights_path_full = Path(artifact.storage_path)
                    print(f"      Storage path: {weights_path_full}")
                    print(f"      Storage path exists: {weights_path_full.exists()}")

        finally:
            await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_check_data.py <dataset_id> <model_id>")
        sys.exit(1)

    dataset_id = sys.argv[1]
    model_id = sys.argv[2]
    asyncio.run(check_data(dataset_id, model_id))
