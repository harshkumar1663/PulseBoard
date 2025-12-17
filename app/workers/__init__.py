"""Workers package initialization."""
from app.workers.celery_app import celery_app
from app.workers.tasks import (
    process_event_task,
    aggregate_metrics_task,
    cleanup_old_events_task,
    send_metric_alert_task,
)

__all__ = [
    "celery_app",
    "process_event_task",
    "aggregate_metrics_task",
    "cleanup_old_events_task",
    "send_metric_alert_task",
]
