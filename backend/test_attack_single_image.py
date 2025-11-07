"""
Test attack on a single image
"""
import asyncio
import sys
import cv2
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app import crud
from app.services.estimator_loader_service import estimator_loader
from app.services.model_inference_service import model_inference_service
from art.attacks.evasion import FastGradientMethod


async def test_single_image_attack(dataset_id: str, model_id: str):
    """Test attack on a single image."""

    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Load estimator
            print(f"Loading estimator for model {model_id}...")
            estimator_id = f"test_{model_id}"

            await estimator_loader.load_estimator_from_db(
                db=session,
                model_id=model_id,
                estimator_id=estimator_id,
            )

            estimator_info = model_inference_service.get_estimator(estimator_id)
            estimator = estimator_info["estimator"]
            print(f"✓ Estimator loaded: {type(estimator)}")

            # Load first image from dataset
            print(f"\nLoading image from dataset {dataset_id}...")
            images_db = await crud.image_2d.get_by_dataset(session, dataset_id=dataset_id)

            if not images_db:
                print("✗ No images found")
                return

            img_record = images_db[0]
            img_path = Path(settings.STORAGE_ROOT) / img_record.storage_key
            print(f"  Image path: {img_path}")
            print(f"  Exists: {img_path.exists()}")

            # Load image
            img_bgr = cv2.imread(str(img_path))
            if img_bgr is None:
                print(f"✗ Failed to load image")
                return

            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            print(f"✓ Image loaded: shape={img_rgb.shape}, dtype={img_rgb.dtype}")

            # Create FGSM attack
            print(f"\nCreating FGSM attack...")
            attack = FastGradientMethod(
                estimator=estimator,
                norm=np.inf,
                eps=8.0,  # epsilon in [0, 255] scale
                targeted=False,
                batch_size=1,
            )
            print(f"✓ Attack created")

            # Prepare image for attack
            x = np.expand_dims(img_rgb, axis=0).astype(np.float32)
            print(f"  Input shape: {x.shape}, dtype={x.dtype}")
            print(f"  Input range: [{x.min()}, {x.max()}]")

            # Generate adversarial example
            print(f"\nGenerating adversarial example...")
            try:
                x_adv = attack.generate(x=x)
                print(f"✓ Attack succeeded!")
                print(f"  Output shape: {x_adv.shape}, dtype={x_adv.dtype}")
                print(f"  Output range: [{x_adv.min()}, {x_adv.max()}]")

                # Calculate perturbation
                perturbation = np.abs(x_adv - x).max()
                print(f"  Max perturbation: {perturbation}")

            except Exception as e:
                print(f"✗ Attack failed: {e}")
                import traceback
                traceback.print_exc()

        finally:
            await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_attack_single_image.py <dataset_id> <model_id>")
        sys.exit(1)

    dataset_id = sys.argv[1]
    model_id = sys.argv[2]
    asyncio.run(test_single_image_attack(dataset_id, model_id))
