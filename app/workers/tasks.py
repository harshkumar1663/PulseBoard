"""Celery tasks for background processing."""
from datetime import datetime, timedelta
from typing import Optional
from celery import Task
from sqlalchemy import select, delete

from app.workers.celery_app import celery_app
from app.db.session import async_session_maker
from app.models.event import Event
from app.models.metric import Metric
from app.services.event_service import event_service
from app.services.metric_service import metric_service
from app.db.redis import redis_client


class AsyncTask(Task):
    """Base task class with async database session."""
    
    _session = None
    
    @property
    def session(self):
        """Get or create database session."""
        if self._session is None:
            self._session = async_session_maker()
        return self._session


@celery_app.task(bind=True, name="app.workers.tasks.process_event_task")
def process_event_task(self, event_id: int):
    """Process an event and generate metrics asynchronously."""
    import asyncio
    
    async def _process():
        async with async_session_maker() as session:
            try:
                # Get event
                result = await session.execute(
                    select(Event).where(Event.id == event_id)
                )
                event = result.scalar_one_or_none()
                
                if not event or event.processed:
                    return
                
                # Generate metrics based on event
                # Example: Count events by type
                metric_data = {
                    "metric_name": f"event.{event.event_type}.count",
                    "metric_type": "counter",
                    "value": 1.0,
                    "dimensions": {
                        "event_name": event.event_name,
                        "source": event.source or "unknown"
                    },
                    "time_bucket": "minute",
                    "timestamp": event.event_timestamp
                }
                
                # Create metric (simplified inline creation)
                from app.schemas.metric import MetricCreate
                metric_in = MetricCreate(**metric_data)
                await metric_service.create(session, metric_in)
                
                # Mark event as processed
                event.processed = True
                event.processed_at = datetime.utcnow()
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                raise e
    
    # Run async function
    asyncio.run(_process())


@celery_app.task(name="app.workers.tasks.aggregate_metrics_task")
def aggregate_metrics_task():
    """Aggregate metrics periodically."""
    import asyncio
    
    async def _aggregate():
        async with async_session_maker() as session:
            try:
                # Get unique metric names from last hour
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                
                result = await session.execute(
                    select(Metric.metric_name)
                    .where(Metric.timestamp >= one_hour_ago)
                    .distinct()
                )
                metric_names = [row[0] for row in result.all()]
                
                # Aggregate each metric
                for metric_name in metric_names:
                    aggregation = await metric_service.aggregate_metrics(
                        session,
                        metric_name=metric_name,
                        start_date=one_hour_ago,
                        end_date=datetime.utcnow(),
                        time_bucket="hour"
                    )
                    
                    # Cache aggregated result
                    await redis_client.set(
                        f"metric:hourly:{metric_name}",
                        {
                            "average": aggregation.average,
                            "total": aggregation.total_sum,
                            "count": aggregation.total_count,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                        expire=3600  # 1 hour
                    )
                
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                raise e
    
    asyncio.run(_aggregate())


@celery_app.task(name="app.workers.tasks.cleanup_old_events_task")
def cleanup_old_events_task(days: int = 90):
    """Clean up events older than specified days."""
    import asyncio
    
    async def _cleanup():
        async with async_session_maker() as session:
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                # Delete old processed events
                stmt = delete(Event).where(
                    Event.processed == True,
                    Event.event_timestamp < cutoff_date
                )
                
                result = await session.execute(stmt)
                deleted_count = result.rowcount
                
                await session.commit()
                
                return {"deleted_events": deleted_count, "cutoff_date": cutoff_date.isoformat()}
                
            except Exception as e:
                await session.rollback()
                raise e
    
    return asyncio.run(_cleanup())


@celery_app.task(name="app.workers.tasks.send_metric_alert_task")
def send_metric_alert_task(metric_name: str, value: float, threshold: float):
    """Send alert when metric exceeds threshold."""
    import asyncio
    
    async def _send_alert():
        # Placeholder for alert logic
        # In production, integrate with email, Slack, PagerDuty, etc.
        await redis_client.set(
            f"alert:{metric_name}:{datetime.utcnow().isoformat()}",
            {
                "metric_name": metric_name,
                "value": value,
                "threshold": threshold,
                "timestamp": datetime.utcnow().isoformat(),
            },
            expire=86400  # 24 hours
        )
        
        # Publish alert to Redis channel
        await redis_client.publish(
            "alerts",
            {
                "type": "metric_threshold",
                "metric_name": metric_name,
                "value": value,
                "threshold": threshold,
            }
        )
    
    asyncio.run(_send_alert())
