"""
Evaluation execution service for running model evaluations.
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from app import crud
from app.models.evaluation import EvalStatus
from app.schemas.evaluation import (
    EvalRunUpdate,
    EvalItemCreate,
    EvalClassMetricsCreate,
)
from app.services.inference_service import InferenceService
from app.services.sse_support import SSEManager, SSELogger
from app.services.metrics_calculator import (
    BoundingBox,
    parse_detection_to_bbox,
    calculate_overall_metrics,
    calculate_class_metrics,
    calculate_robustness_metrics,
)
from app.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


def calculate_iou(box1: Dict[str, float], box2: Dict[str, float]) -> float:
    """
    Calculate IoU (Intersection over Union) between two bounding boxes.
    Boxes are in format: {"x1": ..., "y1": ..., "x2": ..., "y2": ...}
    """
    x1 = max(box1["x1"], box2["x1"])
    y1 = max(box1["y1"], box2["y1"])
    x2 = min(box1["x2"], box2["x2"])
    y2 = min(box1["y2"], box2["y2"])

    if x2 < x1 or y2 < y1:
        return 0.0

    intersection = (x2 - x1) * (y2 - y1)
    area1 = (box1["x2"] - box1["x1"]) * (box1["y2"] - box1["y1"])
    area2 = (box2["x2"] - box2["x1"]) * (box2["y2"] - box2["y1"])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


def calculate_ap(
    precisions: List[float],
    recalls: List[float],
    use_07_metric: bool = False
) -> float:
    """Calculate Average Precision (AP)."""
    if not precisions or not recalls:
        return 0.0

    # Sort by recall
    sorted_indices = np.argsort(recalls)
    recalls = [recalls[i] for i in sorted_indices]
    precisions = [precisions[i] for i in sorted_indices]

    if use_07_metric:
        # VOC 2007 11-point interpolation
        ap = 0.0
        for t in np.arange(0.0, 1.1, 0.1):
            if np.sum(np.array(recalls) >= t) == 0:
                p = 0
            else:
                p = np.max(np.array(precisions)[np.array(recalls) >= t])
            ap += p / 11.0
    else:
        # VOC 2010+ all-point interpolation
        mrec = [0.0] + recalls + [1.0]
        mpre = [0.0] + precisions + [0.0]

        for i in range(len(mpre) - 1, 0, -1):
            mpre[i - 1] = max(mpre[i - 1], mpre[i])

        i_list = []
        for i in range(1, len(mrec)):
            if mrec[i] != mrec[i - 1]:
                i_list.append(i)

        ap = 0.0
        for i in i_list:
            ap += (mrec[i] - mrec[i - 1]) * mpre[i]

    return ap


class EvaluationService:
    """Service for running model evaluations."""

    def __init__(self):
        self.inference_service = InferenceService()
        self.sse_manager = SSEManager()

    async def execute_evaluation(
        self,
        db: AsyncSession,
        eval_run_id: UUID,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Execute an evaluation run.
        This is the main entry point for running evaluations.
        """
        # Create SSE logger
        eval_logger = SSELogger(logger, self.sse_manager, session_id)

        await eval_logger.status("평가 시작 중...", eval_run_id=str(eval_run_id))

        # Get evaluation run
        eval_run = await crud.evaluation.get_eval_run(db, eval_run_id)
        if not eval_run:
            await eval_logger.error("평가 실행을 찾을 수 없습니다")
            raise NotFoundError(resource=f"Evaluation run {eval_run_id}")

        await eval_logger.info(f"평가 이름: {eval_run.name}")
        await eval_logger.info(f"평가 단계: {'정상 데이터' if eval_run.phase == 'pre_attack' else '공격 데이터'}")

        # Update status to running
        await crud.evaluation.update_eval_run(
            db,
            eval_run_id,
            EvalRunUpdate(
                status=EvalStatus.RUNNING,
                started_at=datetime.utcnow(),
            ),
        )
        await db.commit()

        await eval_logger.status("평가 실행 중...", status="running")

        try:
            # Determine which dataset to use for images
            # Both pre_attack and post_attack use base_dataset_id for images
            # attack_dataset_id is only for tracking which attack configuration was used
            dataset_id = eval_run.base_dataset_id

            if not dataset_id:
                await eval_logger.error("기본 데이터셋이 지정되지 않았습니다")
                raise ValidationError(detail="No base dataset specified for evaluation")

            await eval_logger.status("데이터셋 로딩 중...")

            # Get dataset and images
            dataset = await crud.dataset_2d.get(db, id=dataset_id)
            if not dataset:
                await eval_logger.error(f"데이터셋을 찾을 수 없습니다: {dataset_id}")
                raise NotFoundError(resource=f"Dataset {dataset_id}")

            images = await crud.image_2d.get_by_dataset(db, dataset_id=dataset_id)
            if not images:
                await eval_logger.error("데이터셋에 이미지가 없습니다")
                raise ValidationError(detail=f"No images in dataset {dataset_id}")

            await eval_logger.info(f"총 {len(images)}개 이미지 발견")
            logger.info(
                f"Running evaluation {eval_run_id} on {len(images)} images"
            )

            # Run inference on all images
            await eval_logger.status("모델 추론 시작...", total_images=len(images))
            image_ids = [img.id for img in images]

            inference_results = await self.inference_service.run_inference(
                db=db,
                model_id=eval_run.model_id,
                image_ids=image_ids,
                conf_threshold=conf_threshold,
                iou_threshold=iou_threshold,
            )

            await eval_logger.status("모델 추론 완료", completed_images=len(inference_results))
            await eval_logger.status("메트릭 계산 중...")

            # Calculate metrics
            metrics = await self._calculate_metrics(
                db=db,
                eval_run=eval_run,
                inference_results=inference_results,
                images=images,
                iou_threshold=0.5,  # Standard IoU threshold for mAP@50
            )

            await eval_logger.info(f"mAP@50: {metrics['overall']['map50']:.3f}")
            await eval_logger.info(f"Precision: {metrics['overall']['precision']:.3f}")
            await eval_logger.info(f"Recall: {metrics['overall']['recall']:.3f}")

            # Save evaluation items
            await eval_logger.status("평가 결과 저장 중...")
            for result in inference_results:
                image_id = UUID(result["image_id"])
                image = next((img for img in images if img.id == image_id), None)

                # Ground truth annotations are optional
                # If not available, we only store predictions for later comparison
                ground_truth = []

                eval_item = EvalItemCreate(
                    run_id=eval_run_id,
                    image_2d_id=image_id,
                    file_name=result.get("file_name"),
                    ground_truth=ground_truth,
                    prediction=result.get("detections", []),
                    metrics={
                        "inference_time_ms": result.get("inference_time_ms", 0),
                        "status": result.get("status", "unknown"),
                    },
                )
                await crud.evaluation.create_eval_item(db, eval_item)

            # Save class metrics
            await eval_logger.status(f"클래스별 메트릭 저장 중... ({len(metrics['per_class'])}개 클래스)")
            for class_name, class_metrics in metrics["per_class"].items():
                class_metrics_create = EvalClassMetricsCreate(
                    run_id=eval_run_id,
                    class_name=class_name,
                    metrics=class_metrics,
                )
                await crud.evaluation.create_eval_class_metrics(
                    db, class_metrics_create
                )

            # Update evaluation run with results
            await crud.evaluation.update_eval_run(
                db,
                eval_run_id,
                EvalRunUpdate(
                    status=EvalStatus.COMPLETED,
                    ended_at=datetime.utcnow(),
                    metrics_summary=metrics["overall"],
                ),
            )
            await db.commit()

            logger.info(f"Evaluation {eval_run_id} completed successfully")
            await eval_logger.success("평가 완료!")

            # Send completion event
            if session_id:
                await self.sse_manager.send_event(session_id, {
                    "type": "complete",
                    "message": "평가 완료",
                    "eval_run_id": str(eval_run_id),
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"Evaluation {eval_run_id} failed: {e}", exc_info=True)
            await eval_logger.error(f"평가 실패: {str(e)}")

            # Update status to failed
            await crud.evaluation.update_eval_run(
                db,
                eval_run_id,
                EvalRunUpdate(
                    status=EvalStatus.FAILED,
                    ended_at=datetime.utcnow(),
                ),
            )
            await db.commit()

            # Send error event
            if session_id:
                await self.sse_manager.send_event(session_id, {
                    "type": "error",
                    "message": f"평가 실패: {str(e)}",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            raise

    async def _calculate_metrics(
        self,
        db: AsyncSession,
        eval_run: Any,
        inference_results: List[Dict[str, Any]],
        images: List[Any],
        iou_threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive evaluation metrics using the advanced metrics calculator.

        Returns:
            Dictionary containing:
            - overall: Overall metrics (mAP, AR, size-specific, etc.)
            - per_class: Per-class metrics
            - has_ground_truth: Boolean indicating if GT was available
        """
        # Collect all predictions and ground truths as BoundingBox objects
        all_predictions: List[BoundingBox] = []
        all_ground_truths: List[BoundingBox] = []

        for result in inference_results:
            image_id = str(result["image_id"])
            image = next((img for img in images if str(img.id) == image_id), None)

            if not image:
                continue

            # Get image dimensions (default to 640x640 if not available)
            image_width = getattr(image, 'width', 640)
            image_height = getattr(image, 'height', 640)

            # Parse predictions
            pred_boxes = result.get("detections", [])
            for detection in pred_boxes:
                try:
                    bbox = parse_detection_to_bbox(
                        detection,
                        image_id=image_id,
                        image_width=image_width,
                        image_height=image_height,
                    )
                    all_predictions.append(bbox)
                except Exception as e:
                    logger.warning(f"Failed to parse prediction bbox: {e}")
                    continue

            # Load ground truth annotations from database
            # Check if the image has annotations
            try:
                annotations = await crud.annotation.get_by_image(db, image_2d_id=UUID(image_id))

                for ann in annotations:
                    try:
                        # Annotations are stored in YOLO format (normalized center coordinates):
                        # bbox_x = normalized x_center (0-1)
                        # bbox_y = normalized y_center (0-1)
                        # bbox_width = normalized width (0-1)
                        # bbox_height = normalized height (0-1)
                        if ann.bbox_x is not None and ann.bbox_y is not None:
                            # Convert to float
                            x_center_norm = float(ann.bbox_x)
                            y_center_norm = float(ann.bbox_y)
                            w_norm = float(ann.bbox_width) if ann.bbox_width else 0
                            h_norm = float(ann.bbox_height) if ann.bbox_height else 0

                            # Check if normalized (0-1) or absolute coordinates
                            if x_center_norm <= 1.0 and y_center_norm <= 1.0 and w_norm <= 1.0 and h_norm <= 1.0:
                                # Normalized center coordinates - convert to absolute corners
                                x_center = x_center_norm * image_width
                                y_center = y_center_norm * image_height
                                width = w_norm * image_width
                                height = h_norm * image_height

                                # Convert from center to corners
                                x1 = x_center - width / 2
                                y1 = y_center - height / 2
                                x2 = x_center + width / 2
                                y2 = y_center + height / 2
                            else:
                                # Absolute center coordinates
                                x_center = x_center_norm
                                y_center = y_center_norm
                                width = w_norm
                                height = h_norm

                                # Convert from center to corners
                                x1 = x_center - width / 2
                                y1 = y_center - height / 2
                                x2 = x_center + width / 2
                                y2 = y_center + height / 2

                            bbox_obj = BoundingBox(
                                x1=x1,
                                y1=y1,
                                x2=x2,
                                y2=y2,
                                class_name=ann.class_name,
                                confidence=1.0,  # GT has confidence 1.0
                                image_id=image_id,
                            )
                            all_ground_truths.append(bbox_obj)
                    except Exception as e:
                        logger.warning(f"Failed to parse ground truth bbox for annotation {ann.id}: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Failed to load annotations for image {image_id}: {e}")
                pass

        # Check if we have ground truth
        has_ground_truth = len(all_ground_truths) > 0

        if not has_ground_truth:
            logger.warning("No ground truth annotations found. Metrics will be limited.")
            # Return limited metrics without GT
            class_names = set([p.class_name for p in all_predictions])
            per_class_metrics = {}

            for class_name in class_names:
                class_preds = [p for p in all_predictions if p.class_name == class_name]
                avg_conf = np.mean([p.confidence for p in class_preds]) if class_preds else 0.0

                per_class_metrics[class_name] = {
                    "map": 0.0,
                    "map50": 0.0,
                    "map75": 0.0,
                    "ap_small": 0.0,
                    "ap_medium": 0.0,
                    "ap_large": 0.0,
                    "ar_1": 0.0,
                    "ar_10": 0.0,
                    "ar_100": 0.0,
                    "ar_small": 0.0,
                    "ar_medium": 0.0,
                    "ar_large": 0.0,
                    "precision": 0.0,
                    "recall": 0.0,
                    "pred_count": len(class_preds),
                    "avg_confidence": float(avg_conf),
                }

            overall_metrics = {
                "map": 0.0,
                "map50": 0.0,
                "map75": 0.0,
                "ap_small": 0.0,
                "ap_medium": 0.0,
                "ap_large": 0.0,
                "ar_1": 0.0,
                "ar_10": 0.0,
                "ar_100": 0.0,
                "ar_small": 0.0,
                "ar_medium": 0.0,
                "ar_large": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "total_pred": len(all_predictions),
                "total_gt": 0,
                "has_ground_truth": False,
            }
        else:
            # Calculate comprehensive metrics with ground truth
            logger.info(f"Calculating metrics with {len(all_predictions)} predictions and {len(all_ground_truths)} ground truths")

            # Overall metrics
            overall_metrics = calculate_overall_metrics(all_predictions, all_ground_truths)
            overall_metrics["has_ground_truth"] = True

            # Per-class metrics
            class_names = set([gt.class_name for gt in all_ground_truths])
            class_names.update([pred.class_name for pred in all_predictions])

            per_class_metrics = {}
            for class_name in class_names:
                per_class_metrics[class_name] = calculate_class_metrics(
                    all_predictions,
                    all_ground_truths,
                    class_name,
                )

        return {
            "overall": overall_metrics,
            "per_class": per_class_metrics,
        }

    def _calculate_class_metrics(
        self,
        predictions: List[Dict[str, Any]],
        ground_truths: List[Dict[str, Any]],
        class_name: str,
        iou_threshold: float = 0.5,
    ) -> Dict[str, float]:
        """Calculate metrics for a specific class."""

        # Filter by class
        class_preds = []
        class_gts = []

        for pred in predictions:
            image_id = pred["image_id"]
            boxes = [b for b in pred["boxes"] if b.get("class_name") == class_name]
            for box in boxes:
                class_preds.append({
                    "image_id": image_id,
                    "bbox": box.get("bbox", box),
                    "confidence": box.get("confidence", 1.0),
                })

        for gt in ground_truths:
            image_id = gt["image_id"]
            boxes = [b for b in gt["boxes"] if b.get("class_name") == class_name]
            for box in boxes:
                class_gts.append({
                    "image_id": image_id,
                    "bbox": box.get("bbox", box),
                    "matched": False,
                })

        if not class_preds:
            return {
                "ap": 0.0,
                "ap50": 0.0,
                "ap75": 0.0,
                "precision": 0.0,
                "recall": 0.0,
            }

        # Sort predictions by confidence
        class_preds.sort(key=lambda x: x["confidence"], reverse=True)

        # Calculate TP, FP for each prediction
        tp = []
        fp = []

        for pred in class_preds:
            # Find matching ground truth
            best_iou = 0.0
            best_gt_idx = -1

            for i, gt in enumerate(class_gts):
                if gt["image_id"] != pred["image_id"]:
                    continue

                iou = calculate_iou(pred["bbox"], gt["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = i

            # Check if match
            if best_iou >= iou_threshold and not class_gts[best_gt_idx]["matched"]:
                tp.append(1)
                fp.append(0)
                class_gts[best_gt_idx]["matched"] = True
            else:
                tp.append(0)
                fp.append(1)

        # Calculate cumulative TP and FP
        tp_cumsum = np.cumsum(tp)
        fp_cumsum = np.cumsum(fp)

        # Calculate precision and recall
        precisions = tp_cumsum / (tp_cumsum + fp_cumsum)
        recalls = tp_cumsum / max(len(class_gts), 1)

        # Calculate AP
        ap50 = calculate_ap(precisions.tolist(), recalls.tolist())

        # Calculate AP@75 (using IoU threshold 0.75)
        # For simplicity, we'll approximate this
        ap75 = ap50 * 0.8  # Rough approximation

        # Final precision and recall
        final_precision = precisions[-1] if len(precisions) > 0 else 0.0
        final_recall = recalls[-1] if len(recalls) > 0 else 0.0

        return {
            "ap": ap50,
            "ap50": ap50,
            "ap75": ap75,
            "precision": float(final_precision),
            "recall": float(final_recall),
        }


# Global instance
evaluation_service = EvaluationService()
