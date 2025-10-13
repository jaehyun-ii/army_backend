"""
Pytest configuration and fixtures.
"""
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from pathlib import Path
import tempfile
import shutil
import os

# Set test environment variables before importing app
os.environ["ENVIRONMENT"] = "testing"
os.environ["STORAGE_ROOT"] = "/tmp/test_storage"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:testpassword@localhost:5433/adversarial_test"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DEBUG"] = "True"
os.environ["CACHE_TYPE"] = "memory"
os.environ["LOG_LEVEL"] = "DEBUG"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from httpx import AsyncClient
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.core.config import settings, Settings
from app.models.user import User


# Test database URL - PostgreSQL
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:testpassword@localhost:5433/adversarial_test"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings():
    """Override settings for testing."""
    return Settings(
        DATABASE_URL=TEST_DATABASE_URL,
        SECRET_KEY="test-secret-key-for-testing-only",
        ENVIRONMENT="testing",
        DEBUG=True,
        STORAGE_ROOT="/tmp/test_storage",
        CACHE_TYPE="memory",
        LOG_LEVEL="DEBUG"
    )


@pytest_asyncio.fixture(scope="function")
async def db_engine(test_settings):
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        poolclass=NullPool
    )

    async with engine.begin() as conn:
        # Create all PostgreSQL enums first
        enum_definitions = [
            "CREATE TYPE annotation_type_enum AS ENUM ('bbox', 'polygon', 'keypoint', 'segmentation');",
            "CREATE TYPE attack_type_enum AS ENUM ('patch', 'noise');",
            "CREATE TYPE patch_3d_method_enum AS ENUM ('texture', 'material', 'uv', 'sticker', 'custom');",
            "CREATE TYPE eval_status_enum AS ENUM ('queued', 'running', 'completed', 'failed', 'aborted');",
            "CREATE TYPE eval_phase_enum AS ENUM ('pre_attack', 'post_attack');",
            "CREATE TYPE dataset_dimension_enum AS ENUM ('2d', '3d');",
            "CREATE TYPE experiment_status_enum AS ENUM ('draft', 'running', 'completed', 'failed', 'archived');",
            "CREATE TYPE model_framework_enum AS ENUM ('pytorch', 'tensorflow', 'onnx', 'tensorrt', 'openvino', 'custom');",
            "CREATE TYPE model_stage_enum AS ENUM ('draft', 'staging', 'production', 'archived');",
            "CREATE TYPE artifact_type_enum AS ENUM ('model', 'weights', 'config', 'labelmap', 'tokenizer', 'calibration', 'support', 'other');",
            "CREATE TYPE rt_run_status_enum AS ENUM ('running', 'completed', 'failed', 'aborted');",
            "CREATE TYPE user_role_enum AS ENUM ('user', 'admin');",
        ]

        for enum_def in enum_definitions:
            await conn.execute(text(f"""
                DO $$ BEGIN
                    {enum_def}
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """))

        # Now create tables
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables and enums after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

        # Drop all enums
        enum_names = [
            "annotation_type_enum", "attack_type_enum", "patch_3d_method_enum",
            "eval_status_enum", "eval_phase_enum", "dataset_dimension_enum",
            "experiment_status_enum", "model_framework_enum", "model_stage_enum",
            "artifact_type_enum", "rt_run_status_enum", "user_role_enum"
        ]
        for enum_name in enum_names:
            await conn.execute(text(f"DROP TYPE IF EXISTS {enum_name} CASCADE"))

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with overridden database."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Initialize attack plugins for testing
    from app.plugins import attack_plugin_registry
    attack_plugin_registry.discover_plugins()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sync_client(db_session):
    """Create synchronous test client."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session) -> User:
    """Create a test user."""
    import bcrypt

    # Hash password using bcrypt directly
    password = "test123"
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Create user directly
    db_user = User(
        email="test@example.com",
        password_hash=password_hash,
        display_name="Test User",
        role="user",  # Use lowercase string directly to match PostgreSQL enum
        is_active=True
    )
    db_session.add(db_user)
    await db_session.commit()
    await db_session.refresh(db_user)

    return db_user


@pytest_asyncio.fixture
async def admin_user(db_session) -> User:
    """Create an admin test user."""
    import bcrypt

    # Hash password using bcrypt directly
    password = "admin123"
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    admin = User(
        email="admin@example.com",
        password_hash=password_hash,
        display_name="Admin User",
        role="admin",  # Use lowercase string directly to match PostgreSQL enum
        is_active=True
    )

    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    return admin


@pytest.fixture
def auth_headers(test_user) -> dict:
    """Create authentication headers."""
    from app.core.security import create_access_token

    access_token = create_access_token(
        data={"sub": test_user.email}
    )

    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def admin_auth_headers(admin_user) -> dict:
    """Create admin authentication headers."""
    from app.core.security import create_access_token

    access_token = create_access_token(
        data={"sub": admin_user.email}
    )

    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(scope="function")
def temp_storage_dir():
    """Create temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest_asyncio.fixture
async def test_dataset(db_session, test_user):
    """Create a test dataset."""
    from app.models.dataset_2d import Dataset2D

    dataset = Dataset2D(
        name="Test Dataset",
        description="Test dataset for unit tests",
        owner_id=test_user.id,
        storage_path="/test/storage/path",
        metadata_={
            "num_images": 10,
            "format": "COCO"
        }
    )

    db_session.add(dataset)
    await db_session.commit()
    await db_session.refresh(dataset)

    return dataset


@pytest_asyncio.fixture
async def test_model_version(db_session, test_user):
    """Create a test model version with artifacts."""
    from app.models.model_repo import ODModel, ODModelVersion, ODModelArtifact
    from pathlib import Path
    import os
    import shutil

    # Create model
    model = ODModel(
        name="YOLOv8n",
        task="object-detection",
        owner_id=test_user.id,
        description="YOLOv8 Nano model for testing"
    )

    db_session.add(model)
    await db_session.flush()

    # Create version
    version = ODModelVersion(
        model_id=model.id,
        version="8.3.0",
        framework="pytorch",
        framework_version="2.0.0",
        input_spec={
            "shape": [640, 640, 3],
            "dtype": "float32"
        },
        labelmap={str(i): name for i, name in enumerate([
            "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
            "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
            "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe",
            "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
            "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
            "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl",
            "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza",
            "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet",
            "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven",
            "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
            "hair drier", "toothbrush"
        ])},
        stage="draft"
    )

    db_session.add(version)
    await db_session.flush()

    # Create model directory and copy all files from test_model
    model_dir = Path("/tmp/test_storage/custom_models") / str(version.id)
    model_dir.mkdir(parents=True, exist_ok=True)

    # Copy all files from test_model directory
    test_model_dir = Path(__file__).parent / "test_model"

    # Copy weights
    yolov8_source = test_model_dir / "yolov8n.pt"
    weights_path = model_dir / "yolov8n.pt"

    # Copy config
    config_source = test_model_dir / "yolov8_config.yaml"
    config_path = model_dir / "config.yaml"

    # Copy adapter
    adapter_source = test_model_dir / "yolov8_adapter.py"
    adapter_path = model_dir / "adapter.py"

    if yolov8_source.exists() and config_source.exists() and adapter_source.exists():
        shutil.copy(yolov8_source, weights_path)
        shutil.copy(config_source, config_path)
        shutil.copy(adapter_source, adapter_path)
        size_bytes = weights_path.stat().st_size
    else:
        # Fallback: try backend directory
        yolov8_backup = Path(__file__).parent.parent / "yolov8n.pt"
        config_backup = Path(__file__).parent.parent / "yolov8_config.yaml"
        adapter_backup = Path(__file__).parent.parent / "yolov8_adapter.py"

        if yolov8_backup.exists() and config_backup.exists() and adapter_backup.exists():
            shutil.copy(yolov8_backup, weights_path)
            shutil.copy(config_backup, config_path)
            shutil.copy(adapter_backup, adapter_path)
            size_bytes = weights_path.stat().st_size
        else:
            # Last resort: fake weights
            weights_path.write_bytes(b"fake model weights for testing")
            size_bytes = len(b"fake model weights for testing")

    # Create artifacts record
    artifact = ODModelArtifact(
        model_version_id=version.id,
        artifact_type="weights",
        storage_key=str(version.id),
        file_name="yolov8n.pt",
        size_bytes=size_bytes
    )

    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(version)

    return version


@pytest.fixture
def mock_image_file():
    """Create a mock image file."""
    import io
    from PIL import Image

    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    return img_bytes


@pytest.fixture
def mock_model_file(temp_storage_dir):
    """Create a mock model file."""
    model_path = temp_storage_dir / "test_model.pt"
    model_path.write_bytes(b"fake model data")
    return model_path


# Markers for different test types
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_gpu: mark test as requiring GPU"
    )