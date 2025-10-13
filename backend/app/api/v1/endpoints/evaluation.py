"""
API endpoints for evaluation operations.
"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.crud import evaluation as crud_evaluation
from app.schemas.evaluation import (
    EvalRunCreate,
    EvalRunUpdate,
    EvalRunResponse,
    EvalRunListResponse,
    EvalItemCreate,
    EvalItemUpdate,
    EvalItemResponse,
    EvalItemListResponse,
    EvalClassMetricsCreate,
    EvalClassMetricsUpdate,
    EvalClassMetricsResponse,
    EvalClassMetricsListResponse,
    EvalListCreate,
    EvalListUpdate,
    EvalListResponse,
    EvalListListResponse,
    EvalListItemCreate,
    EvalListItemResponse,
    EvalRunPairResponse,
    EvalRunPairDeltaResponse,
    EvalStatus,
    EvalPhase,
)

router = APIRouter()


# ========== Evaluation Run Endpoints ==========

@router.post("/runs", response_model=EvalRunResponse, status_code=status.HTTP_201_CREATED)
async def create_evaluation_run(
    eval_run: EvalRunCreate,
    db: AsyncSession = Depends(get_db),
    # current_user: User = Depends(get_current_user),  # TODO: Add auth
):
    """
    Create a new evaluation run.

    - **pre_attack**: Requires base_dataset_id
    - **post_attack**: Requires attack_dataset_id (base_dataset_id auto-validated)
    """
    try:
        db_eval_run = await crud_evaluation.create_eval_run(
            db=db,
            eval_run=eval_run,
            # created_by=current_user.id,  # TODO: Add auth
        )
        return db_eval_run
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
async def get_evaluation_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation run by ID."""
    db_eval_run = await crud_evaluation.get_eval_run(db=db, eval_run_id=run_id)
    if not db_eval_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )
    return db_eval_run


@router.get("/runs", response_model=EvalRunListResponse)
async def list_evaluation_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    phase: Optional[EvalPhase] = None,
    status_filter: Optional[EvalStatus] = Query(None, alias="status"),
    model_version_id: Optional[UUID] = None,
    base_dataset_id: Optional[UUID] = None,
    attack_dataset_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List evaluation runs with filters and pagination.

    Filters:
    - **phase**: pre_attack or post_attack
    - **status**: queued, running, completed, failed, aborted
    - **model_version_id**: Filter by model version
    - **base_dataset_id**: Filter by base dataset
    - **attack_dataset_id**: Filter by attack dataset
    """
    skip = (page - 1) * page_size
    items, total = await crud_evaluation.get_eval_runs(
        db=db,
        skip=skip,
        limit=page_size,
        phase=phase,
        status=status_filter,
        model_version_id=model_version_id,
        base_dataset_id=base_dataset_id,
        attack_dataset_id=attack_dataset_id,
    )
    return EvalRunListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/runs/{run_id}", response_model=EvalRunResponse)
async def update_evaluation_run(
    run_id: UUID,
    eval_run_update: EvalRunUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update evaluation run (status, metrics, timestamps, etc.)."""
    db_eval_run = await crud_evaluation.update_eval_run(
        db=db,
        eval_run_id=run_id,
        eval_run_update=eval_run_update,
    )
    if not db_eval_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )
    return db_eval_run


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete evaluation run."""
    success = await crud_evaluation.delete_eval_run(db=db, eval_run_id=run_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found",
        )


# ========== Evaluation Item Endpoints ==========

@router.post("/items", response_model=EvalItemResponse, status_code=status.HTTP_201_CREATED)
async def create_evaluation_item(
    eval_item: EvalItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new evaluation item (per-image result)."""
    try:
        db_eval_item = await crud_evaluation.create_eval_item(db=db, eval_item=eval_item)
        return db_eval_item
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/items/bulk", response_model=List[EvalItemResponse], status_code=status.HTTP_201_CREATED)
async def create_evaluation_items_bulk(
    eval_items: List[EvalItemCreate],
    db: AsyncSession = Depends(get_db),
):
    """Create multiple evaluation items in bulk."""
    try:
        db_eval_items = await crud_evaluation.create_eval_items_bulk(db=db, eval_items=eval_items)
        return db_eval_items
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/items/{item_id}", response_model=EvalItemResponse)
async def get_evaluation_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation item by ID."""
    db_eval_item = await crud_evaluation.get_eval_item(db=db, eval_item_id=item_id)
    if not db_eval_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation item not found",
        )
    return db_eval_item


@router.get("/runs/{run_id}/items", response_model=EvalItemListResponse)
async def list_evaluation_items(
    run_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List all evaluation items for a specific run."""
    skip = (page - 1) * page_size
    items, total = await crud_evaluation.get_eval_items(
        db=db,
        run_id=run_id,
        skip=skip,
        limit=page_size,
    )
    return EvalItemListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/items/{item_id}", response_model=EvalItemResponse)
async def update_evaluation_item(
    item_id: UUID,
    eval_item_update: EvalItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update evaluation item."""
    db_eval_item = await crud_evaluation.update_eval_item(
        db=db,
        eval_item_id=item_id,
        eval_item_update=eval_item_update,
    )
    if not db_eval_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation item not found",
        )
    return db_eval_item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete evaluation item."""
    success = await crud_evaluation.delete_eval_item(db=db, eval_item_id=item_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation item not found",
        )


# ========== Evaluation Class Metrics Endpoints ==========

@router.post("/class-metrics", response_model=EvalClassMetricsResponse, status_code=status.HTTP_201_CREATED)
async def create_class_metrics(
    metrics: EvalClassMetricsCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create per-class metrics for an evaluation run."""
    try:
        db_metrics = await crud_evaluation.create_eval_class_metrics(db=db, metrics=metrics)
        return db_metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/class-metrics/bulk", response_model=List[EvalClassMetricsResponse], status_code=status.HTTP_201_CREATED)
async def create_class_metrics_bulk(
    metrics_list: List[EvalClassMetricsCreate],
    db: AsyncSession = Depends(get_db),
):
    """Create multiple class metrics in bulk."""
    try:
        db_metrics_list = await crud_evaluation.create_eval_class_metrics_bulk(
            db=db,
            metrics_list=metrics_list,
        )
        return db_metrics_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/runs/{run_id}/class-metrics", response_model=EvalClassMetricsListResponse)
async def list_class_metrics(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all class metrics for an evaluation run."""
    items = await crud_evaluation.get_eval_class_metrics(db=db, run_id=run_id)
    return EvalClassMetricsListResponse(
        items=items,
        total=len(items),
    )


@router.patch("/class-metrics/{metrics_id}", response_model=EvalClassMetricsResponse)
async def update_class_metrics(
    metrics_id: UUID,
    metrics_update: EvalClassMetricsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update class metrics."""
    db_metrics = await crud_evaluation.update_eval_class_metrics(
        db=db,
        metrics_id=metrics_id,
        metrics_update=metrics_update,
    )
    if not db_metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class metrics not found",
        )
    return db_metrics


# Note: Evaluation Lists and Comparison endpoints removed as they are not used by frontend
# The database tables (eval_lists, eval_list_items) and views (eval_run_pairs, eval_run_pairs_delta)
# remain in the database schema for potential future use.
