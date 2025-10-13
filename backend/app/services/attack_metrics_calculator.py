"""
Attack metrics calculation service.

This module is responsible for calculating and comparing attack effectiveness metrics
based on pre-attack and post-attack evaluation results.

Separated from AttackService to follow single responsibility principle.
"""
from typing import Any, Dict, Optional
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class AttackMetricsCalculator:
    """
    Calculate attack effectiveness metrics.

    This class handles metric calculation logic for comparing
    pre-attack and post-attack evaluation results.
    """

    @staticmethod
    def calculate_drop_percentage(pre_value: float, post_value: float) -> float:
        """
        Calculate percentage drop between pre and post values.

        Args:
            pre_value: Pre-attack metric value
            post_value: Post-attack metric value

        Returns:
            Percentage drop (0-100)
        """
        if pre_value == 0:
            return 0.0
        return ((pre_value - post_value) / pre_value) * 100

    @staticmethod
    def calculate_effectiveness(pre_value: float, post_value: float) -> float:
        """
        Calculate attack effectiveness score (0-1).

        Args:
            pre_value: Pre-attack metric value
            post_value: Post-attack metric value

        Returns:
            Effectiveness score (0-1)
        """
        if pre_value == 0:
            return 0.0
        return (pre_value - post_value) / pre_value

    def calculate_comparative_metrics(
        self,
        pre_metrics: Dict[str, Any],
        post_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculate comparative metrics from pre and post evaluation results.

        Args:
            pre_metrics: Pre-attack metrics summary
            post_metrics: Post-attack metrics summary

        Returns:
            Dictionary with comparative metrics including drops and effectiveness
        """
        # Extract metric values
        map_50_pre = pre_metrics.get("mAP_50", 0.0)
        map_50_post = post_metrics.get("mAP_50", 0.0)

        precision_pre = pre_metrics.get("precision", 0.0)
        precision_post = post_metrics.get("precision", 0.0)

        recall_pre = pre_metrics.get("recall", 0.0)
        recall_post = post_metrics.get("recall", 0.0)

        # Calculate drops and effectiveness
        return {
            "pre_attack_mAP_50": map_50_pre,
            "post_attack_mAP_50": map_50_post,
            "mAP_50_drop": map_50_pre - map_50_post,
            "mAP_50_drop_percentage": self.calculate_drop_percentage(
                map_50_pre, map_50_post
            ),
            "pre_attack_precision": precision_pre,
            "post_attack_precision": precision_post,
            "precision_drop": precision_pre - precision_post,
            "pre_attack_recall": recall_pre,
            "post_attack_recall": recall_post,
            "recall_drop": recall_pre - recall_post,
            "attack_effectiveness": self.calculate_effectiveness(
                map_50_pre, map_50_post
            ),
            "status": "completed",
        }

    def calculate_basic_metrics(
        self,
        attack_metadata: Dict[str, Any],
        attack_method: Optional[str],
        hyperparameters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculate basic metrics when evaluation results are not available.

        Args:
            attack_metadata: Attack metadata dictionary
            attack_method: Attack method name
            hyperparameters: Attack hyperparameters

        Returns:
            Dictionary with basic attack statistics
        """
        return {
            "total_images": attack_metadata.get("total_images", 0),
            "method": attack_method,
            "hyperparameters": hyperparameters,
            "status": "basic_stats_only",
        }

    async def calculate_attack_metrics(
        self,
        db: AsyncSession,
        attack_id: UUID,
        pre_attack_eval_id: Optional[UUID] = None,
        post_attack_eval_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Calculate metrics comparing pre/post attack evaluations when available.

        Args:
            db: Database session
            attack_id: Attack dataset ID
            pre_attack_eval_id: Optional pre-attack evaluation ID
            post_attack_eval_id: Optional post-attack evaluation ID

        Returns:
            Dictionary with calculated metrics

        Raises:
            NotFoundError: If attack not found
        """
        # Fetch attack dataset
        attack = await crud.attack_dataset_2d.get(db, id=attack_id)
        if not attack:
            raise NotFoundError(resource=f"Attack dataset {attack_id}")

        logger.info("Calculating metrics for attack: %s", attack.name)

        # Base metrics
        metrics: Dict[str, Any] = {
            "attack_id": str(attack_id),
            "attack_type": attack.attack_type.value,
        }

        # Calculate comparative metrics if evaluations provided
        if pre_attack_eval_id and post_attack_eval_id:
            pre_eval = await crud.evaluation_run.get(db, id=pre_attack_eval_id)
            post_eval = await crud.evaluation_run.get(db, id=post_attack_eval_id)

            if pre_eval and post_eval:
                pre_metrics = pre_eval.metrics_summary or {}
                post_metrics = post_eval.metrics_summary or {}

                comparative = self.calculate_comparative_metrics(
                    pre_metrics, post_metrics
                )
                metrics.update(comparative)
            else:
                metrics["status"] = "evaluation_not_found"
        else:
            # Calculate basic metrics when evaluations not provided
            metadata = attack.attack_metadata or {}
            basic = self.calculate_basic_metrics(
                metadata, attack.method, attack.hyperparameters
            )
            metrics.update(basic)

        return metrics


# Singleton instance
attack_metrics_calculator = AttackMetricsCalculator()
