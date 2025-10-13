"""
Real-time performance measurement models (simplified).
"""
from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, ForeignKey, Boolean, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class RTRunStatus(str, enum.Enum):
    """Real-time capture run status enum."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class Camera(Base):
    """Camera model."""

    __tablename__ = "cameras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    stream_uri = Column(Text)
    location = Column(JSONB)
    resolution = Column(JSONB)
    metadata_ = Column("metadata", JSONB)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("char_length(name) > 0", name="chk_camera_name"),
        CheckConstraint("resolution IS NULL OR jsonb_typeof(resolution)='object'", name="chk_camera_resolution"),
    )


class RTCaptureRun(Base):
    """Real-time capture run model."""

    __tablename__ = "rt_capture_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="RESTRICT"), nullable=False)
    model_version_id = Column(
        UUID(as_uuid=True), ForeignKey("od_model_versions.id", ondelete="RESTRICT"), nullable=False
    )
    window_seconds = Column(Integer, nullable=False, default=5)
    frames_expected = Column(Integer, nullable=False, default=10)
    fps_target = Column(Numeric(6, 3))
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    status = Column(SQLEnum(RTRunStatus, name="rt_run_status_enum", values_callable=lambda x: [e.value for e in x]), nullable=False, default=RTRunStatus.RUNNING.value)
    notes = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("window_seconds > 0", name="chk_rt_window"),
        CheckConstraint("frames_expected > 0", name="chk_rt_frames_expected"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="chk_rt_run_time_range"),
        CheckConstraint("fps_target IS NULL OR fps_target > 0", name="chk_rt_fps_positive"),
    )


class RTFrame(Base):
    """Real-time frame model."""

    __tablename__ = "rt_frames"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("rt_capture_runs.id", ondelete="CASCADE"), nullable=False)
    seq_no = Column(Integer, nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    storage_key = Column(Text)
    width = Column(Integer)
    height = Column(Integer)
    mime_type = Column(String(100))
    metadata_ = Column("metadata", JSONB)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("seq_no > 0", name="chk_rt_frames_seq"),
        CheckConstraint(
            "(width IS NULL AND height IS NULL) OR (width > 0 AND height > 0)", name="chk_rt_frames_wh"
        ),
    )


class RTInference(Base):
    """Real-time inference model."""

    __tablename__ = "rt_inferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    frame_id = Column(UUID(as_uuid=True), ForeignKey("rt_frames.id", ondelete="CASCADE"), nullable=False)
    model_version_id = Column(
        UUID(as_uuid=True), ForeignKey("od_model_versions.id", ondelete="RESTRICT"), nullable=False
    )
    latency_ms = Column(Integer)
    inference = Column(JSONB, nullable=False)
    stats = Column(JSONB)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("jsonb_typeof(inference)='object'", name="chk_rt_inf_json"),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="chk_rt_inf_latency_nonneg"),
    )
