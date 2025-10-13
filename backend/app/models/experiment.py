"""
Experiment models.
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class ExperimentStatus(str, enum.Enum):
    """Experiment status enum."""

    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class Experiment(Base):
    """Experiment model for research organization."""

    __tablename__ = "experiments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    objective = Column(Text)
    hypothesis = Column(Text)
    status = Column(SQLEnum(ExperimentStatus, name="experiment_status_enum", values_callable=lambda x: [e.value for e in x]), nullable=False, default=ExperimentStatus.DRAFT.value)
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    tags = Column(JSONB)
    config = Column(JSONB)
    results_summary = Column(JSONB)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    attack_datasets_2d = relationship("AttackDataset2D", back_populates="experiment")
    eval_runs = relationship("EvalRun", back_populates="experiment")

    __table_args__ = (
        CheckConstraint("char_length(name) > 0", name="chk_experiment_name"),
        CheckConstraint(
            "(status = 'draft' AND started_at IS NULL AND ended_at IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL AND ended_at IS NULL) OR "
            "(status IN ('completed', 'failed', 'archived') AND started_at IS NOT NULL AND ended_at IS NOT NULL AND ended_at >= started_at)",
            name="chk_experiment_status_time",
        ),
        CheckConstraint("tags IS NULL OR jsonb_typeof(tags) = 'array'", name="chk_experiment_tags"),
        CheckConstraint("config IS NULL OR jsonb_typeof(config) = 'object'", name="chk_experiment_config"),
        CheckConstraint("results_summary IS NULL OR jsonb_typeof(results_summary) = 'object'", name="chk_experiment_results"),
    )
