"""
CRUD operations for experiments.
"""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime

from app.models.experiment import Experiment, ExperimentStatus
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate
from app.crud.base import CRUDBase


class CRUDExperiment(CRUDBase[Experiment, ExperimentCreate, ExperimentUpdate]):
    """CRUD operations for Experiment model."""

    def get_by_status(
        self, db: Session, *, status: ExperimentStatus, skip: int = 0, limit: int = 100
    ) -> List[Experiment]:
        """Get experiments by status."""
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.status == status,
                    self.model.deleted_at.is_(None)
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def start_experiment(self, db: Session, *, experiment_id: UUID) -> Optional[Experiment]:
        """Start an experiment (update status and started_at)."""
        experiment = self.get(db, id=experiment_id)
        if experiment and experiment.status == ExperimentStatus.DRAFT:
            experiment.status = ExperimentStatus.RUNNING
            experiment.started_at = datetime.utcnow()
            db.commit()
            db.refresh(experiment)
        return experiment

    def complete_experiment(
        self, db: Session, *, experiment_id: UUID, results_summary: dict
    ) -> Optional[Experiment]:
        """Complete an experiment (update status, ended_at, and results_summary)."""
        experiment = self.get(db, id=experiment_id)
        if experiment and experiment.status == ExperimentStatus.RUNNING:
            experiment.status = ExperimentStatus.COMPLETED
            experiment.ended_at = datetime.utcnow()
            experiment.results_summary = results_summary
            db.commit()
            db.refresh(experiment)
        return experiment

    def fail_experiment(self, db: Session, *, experiment_id: UUID) -> Optional[Experiment]:
        """Fail an experiment (update status and ended_at)."""
        experiment = self.get(db, id=experiment_id)
        if experiment and experiment.status == ExperimentStatus.RUNNING:
            experiment.status = ExperimentStatus.FAILED
            experiment.ended_at = datetime.utcnow()
            db.commit()
            db.refresh(experiment)
        return experiment


experiment = CRUDExperiment(Experiment)
