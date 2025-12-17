"""Celery application configuration."""
from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "pulseboard",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)

# Periodic tasks (beat schedule)
celery_app.conf.beat_schedule = {
    "aggregate-metrics-every-minute": {
        "task": "app.workers.tasks.aggregate_metrics_task",
        "schedule": 60.0,  # Every minute
    },
    "cleanup-old-events-daily": {
        "task": "app.workers.tasks.cleanup_old_events_task",
        "schedule": 86400.0,  # Every 24 hours
    },
}
