"""
Model repository models.
"""
from sqlalchemy import Column, String, Text, Integer, BigInteger, DateTime, ForeignKey, Boolean, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class ModelFramework(str, enum.Enum):
    """Model framework enum."""

    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    OPENVINO = "openvino"
    CUSTOM = "custom"


class ModelStage(str, enum.Enum):
    """Model lifecycle stage enum."""

    DRAFT = "draft"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class ArtifactType(str, enum.Enum):
    """Model artifact type enum."""

    MODEL = "model"
    WEIGHTS = "weights"
    CONFIG = "config"
    LABELMAP = "labelmap"
    TOKENIZER = "tokenizer"
    CALIBRATION = "calibration"
    SUPPORT = "support"
    OTHER = "other"


class ODModel(Base):
    """Object detection model catalog."""

    __tablename__ = "od_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    task = Column(String(50), nullable=False, default="object-detection")
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    description = Column(Text)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    versions = relationship("ODModelVersion", back_populates="model", lazy="selectin")

    __table_args__ = (CheckConstraint("char_length(task) > 0", name="chk_od_models_task"),)


class ODModelVersion(Base):
    """Versioned model instances."""

    __tablename__ = "od_model_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("od_models.id", ondelete="CASCADE"), nullable=False)
    version = Column(String(64), nullable=False)
    framework = Column(SQLEnum(ModelFramework, name="model_framework_enum", values_callable=lambda x: [e.value for e in x]), nullable=False)
    framework_version = Column(String(64))
    input_spec = Column(JSONB)
    training_metadata = Column(JSONB)
    labelmap = Column(JSONB)
    inference_params = Column(JSONB)
    stage = Column(SQLEnum(ModelStage, name="model_stage_enum", values_callable=lambda x: [e.value for e in x]), nullable=False, default=ModelStage.DRAFT.value)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    published_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    model = relationship("ODModel", back_populates="versions")
    classes = relationship("ODModelClass", back_populates="model_version", lazy="selectin")
    artifacts = relationship("ODModelArtifact", back_populates="model_version", lazy="selectin")
    deployments = relationship("ODModelDeployment", back_populates="model_version", lazy="selectin")

    __table_args__ = (
        CheckConstraint("input_spec IS NULL OR jsonb_typeof(input_spec)='object'", name="chk_input_spec"),
        CheckConstraint("labelmap IS NULL OR jsonb_typeof(labelmap)='object'", name="chk_labelmap"),
        CheckConstraint(
            "inference_params IS NULL OR jsonb_typeof(inference_params)='object'", name="chk_inference_params"
        ),
    )


class ODModelClass(Base):
    """Model class definitions."""

    __tablename__ = "od_model_classes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(
        UUID(as_uuid=True), ForeignKey("od_model_versions.id", ondelete="CASCADE"), nullable=False
    )
    class_index = Column(Integer, nullable=False)
    class_name = Column(String(200), nullable=False)
    metadata_ = Column("metadata", JSONB)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    model_version = relationship("ODModelVersion", back_populates="classes")

    __table_args__ = (
        CheckConstraint("char_length(class_name) > 0", name="chk_class_name"),
        CheckConstraint("class_index >= 0", name="chk_class_index"),
        CheckConstraint("metadata IS NULL OR jsonb_typeof(metadata)='object'", name="chk_class_metadata"),
    )


class ODModelArtifact(Base):
    """Model artifacts (files, weights, configs)."""

    __tablename__ = "od_model_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(
        UUID(as_uuid=True), ForeignKey("od_model_versions.id", ondelete="CASCADE"), nullable=False
    )
    artifact_type = Column(SQLEnum(ArtifactType, name="artifact_type_enum", values_callable=lambda x: [e.value for e in x]), nullable=False)
    storage_key = Column(Text, nullable=False)
    file_name = Column(String(1024), nullable=False)
    size_bytes = Column(BigInteger)
    sha256 = Column(String(64))
    content_type = Column(String(200))
    metadata_ = Column("metadata", JSONB)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    model_version = relationship("ODModelVersion", back_populates="artifacts")

    __table_args__ = (
        CheckConstraint("metadata IS NULL OR jsonb_typeof(metadata)='object'", name="chk_artifact_metadata"),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="chk_artifact_size_nonneg"),
    )

    @property
    def storage_path(self) -> str:
        """Get full storage path for artifact."""
        from app.core.config import settings
        from pathlib import Path
        return str(Path(settings.STORAGE_ROOT) / "custom_models" / self.storage_key / self.file_name)


class ODModelDeployment(Base):
    """Model deployment endpoints."""

    __tablename__ = "od_model_deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version_id = Column(
        UUID(as_uuid=True), ForeignKey("od_model_versions.id", ondelete="CASCADE"), nullable=False
    )
    endpoint_url = Column(Text)
    runtime = Column(JSONB)
    region = Column(String(64))
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    model_version = relationship("ODModelVersion", back_populates="deployments")

    __table_args__ = (CheckConstraint("runtime IS NULL OR jsonb_typeof(runtime)='object'", name="chk_runtime"),)
