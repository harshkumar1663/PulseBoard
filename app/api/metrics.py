"""Metric routes."""
from typing import List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_active_user
from app.models.user import User
from app.schemas.metric import MetricCreate, MetricResponse, MetricFilter, MetricAggregation
from app.services.metric_service import metric_service

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.post("/", response_model=MetricResponse, status_code=status.HTTP_201_CREATED)
async def create_metric(
    metric_in: MetricCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new metric data point."""
    metric = await metric_service.create(db, metric_in)
    
    # Cache for quick access
    await metric_service.cache_metric(metric.metric_name, metric.value)
    
    return metric


@router.get("/", response_model=List[MetricResponse])
async def get_metrics(
    filters: MetricFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get metrics with filters."""
    metrics = await metric_service.get_metrics(db, filters)
    return metrics


@router.get("/{metric_id}", response_model=MetricResponse)
async def get_metric(
    metric_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific metric."""
    metric = await metric_service.get_by_id(db, metric_id)
    
    if not metric:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metric not found"
        )
    
    return metric


@router.get("/aggregate/{metric_name}", response_model=MetricAggregation)
async def aggregate_metric(
    metric_name: str,
    start_date: datetime = Query(default_factory=lambda: datetime.utcnow() - timedelta(days=1)),
    end_date: datetime = Query(default_factory=datetime.utcnow),
    time_bucket: str = Query(default="hour", pattern="^(minute|hour|day)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get aggregated metrics over a time range."""
    aggregation = await metric_service.aggregate_metrics(
        db,
        metric_name=metric_name,
        start_date=start_date,
        end_date=end_date,
        time_bucket=time_bucket
    )
    return aggregation


@router.get("/latest/{metric_name}")
async def get_latest_metric(
    metric_name: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get latest cached metric value."""
    cached = await metric_service.get_cached_metric(metric_name)
    
    if not cached:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metric not found in cache"
        )
    
    return cached
