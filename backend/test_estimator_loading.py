"""
Test estimator loading directly
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app import crud
from app.services.estimator_loader_service import estimator_loader
from app.services.model_inference_service import model_inference_service


async def test_estimator_loading(model_id: str):
    """Test loading estimator from model."""

    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            print(f"Loading estimator for model {model_id}...")

            # Load estimator
            estimator_id = f"test_{model_id}"

            try:
                await estimator_loader.load_estimator_from_db(
                    db=session,
                    model_id=model_id,
                    estimator_id=estimator_id,
                )
                print(f"✓ Estimator loaded successfully!")

                # Check if it's registered
                estimator_info = model_inference_service.get_estimator(estimator_id)
                if estimator_info:
                    print(f"✓ Estimator registered in service")
                    print(f"  Type: {type(estimator_info['estimator'])}")
                    print(f"  Metadata: {estimator_info.get('metadata', {})}")
                else:
                    print(f"✗ Estimator not found in service")

            except Exception as e:
                print(f"✗ Failed to load estimator: {e}")
                import traceback
                traceback.print_exc()

        finally:
            await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_estimator_loading.py <model_id>")
        sys.exit(1)

    model_id = sys.argv[1]
    asyncio.run(test_estimator_loading(model_id))
