"""Metric service for business logic."""
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.models.metric import Metric
from app.schemas.metric import MetricCreate, MetricFilter, MetricAggregation
from app.db.redis import redis_client


class MetricService:
    """Service layer for metric operations."""
    
    @staticmethod
    async def create(db: AsyncSession, metric_in: MetricCreate) -> Metric:
        """Create new metric."""
        timestamp = metric_in.timestamp or datetime.utcnow()
        
        # Round timestamp based on time bucket
        if metric_in.time_bucket == "minute":
            timestamp = timestamp.replace(second=0, microsecond=0)
        elif metric_in.time_bucket == "hour":
            timestamp = timestamp.replace(minute=0, second=0, microsecond=0)
        elif metric_in.time_bucket == "day":
            timestamp = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        
        metric = Metric(
            metric_name=metric_in.metric_name,
            metric_type=metric_in.metric_type,
            value=metric_in.value,
            dimensions=metric_in.dimensions,
            tags=metric_in.tags,
            time_bucket=metric_in.time_bucket,
            timestamp=timestamp,
            count=1,
            min_value=metric_in.value,
            max_value=metric_in.value,
            sum_value=metric_in.value,
            avg_value=metric_in.value,
        )
        
        db.add(metric)
        await db.commit()
        await db.refresh(metric)
        
        # Publish to Redis for real-time updates
        await redis_client.publish(
            "metrics:updates",
            {
                "metric_name": metric.metric_name,
                "value": metric.value,
                "timestamp": metric.timestamp.isoformat(),
                "dimensions": metric.dimensions,
            }
        )
        
        return metric
    
    @staticmethod
    async def get_by_id(db: AsyncSession, metric_id: int) -> Optional[Metric]:
        """Get metric by ID."""
        result = await db.execute(select(Metric).where(Metric.id == metric_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_metrics(db: AsyncSession, filters: MetricFilter) -> List[Metric]:
        """Get metrics with filters."""
        query = select(Metric)
        
        # Apply filters
        conditions = []
        if filters.metric_name:
            conditions.append(Metric.metric_name == filters.metric_name)
        if filters.metric_type:
            conditions.append(Metric.metric_type == filters.metric_type)
        if filters.time_bucket:
            conditions.append(Metric.time_bucket == filters.time_bucket)
        if filters.start_date:
            conditions.append(Metric.timestamp >= filters.start_date)
        if filters.end_date:
            conditions.append(Metric.timestamp <= filters.end_date)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(Metric.timestamp.desc())
        query = query.limit(filters.limit).offset(filters.offset)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def aggregate_metrics(
        db: AsyncSession,
        metric_name: str,
        start_date: datetime,
        end_date: datetime,
        time_bucket: str = "hour"
    ) -> MetricAggregation:
        """Aggregate metrics over time range."""
        query = select(
            func.count(Metric.id).label("total_count"),
            func.sum(Metric.sum_value).label("total_sum"),
            func.avg(Metric.avg_value).label("average"),
            func.min(Metric.min_value).label("minimum"),
            func.max(Metric.max_value).label("maximum"),
        ).where(
            and_(
                Metric.metric_name == metric_name,
                Metric.time_bucket == time_bucket,
                Metric.timestamp >= start_date,
                Metric.timestamp <= end_date,
            )
        )
        
        result = await db.execute(query)
        row = result.one()
        
        # Get metric type
        metric_query = select(Metric.metric_type).where(
            Metric.metric_name == metric_name
        ).limit(1)
        metric_result = await db.execute(metric_query)
        metric_type = metric_result.scalar_one_or_none() or "unknown"
        
        return MetricAggregation(
            metric_name=metric_name,
            metric_type=metric_type,
            time_bucket=time_bucket,
            total_count=row.total_count or 0,
            total_sum=row.total_sum or 0.0,
            average=row.average or 0.0,
            minimum=row.minimum or 0.0,
            maximum=row.maximum or 0.0,
            start_time=start_date,
            end_time=end_date,
        )
    
    @staticmethod
    async def cache_metric(metric_name: str, value: float, ttl: int = 60) -> None:
        """Cache metric value in Redis."""
        await redis_client.set(
            f"metric:latest:{metric_name}",
            {"value": value, "timestamp": datetime.utcnow().isoformat()},
            expire=ttl
        )
    
    @staticmethod
    async def get_cached_metric(metric_name: str) -> Optional[dict]:
        """Get cached metric from Redis."""
        return await redis_client.get(f"metric:latest:{metric_name}")


metric_service = MetricService()
