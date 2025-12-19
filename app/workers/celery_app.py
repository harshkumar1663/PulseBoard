"""Celery application configuration."""
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "pulseboard",
    broker=settings.CELERY_BROKER,
    backend=settings.CELERY_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    result_expires=3600,
    result_extended=True,
)

# Celery event settings
celery_app.conf.task_time_limit = 30 * 60  # 30 minutes hard limit
celery_app.conf.task_soft_time_limit = 25 * 60  # 25 minutes soft limit


# Task lifecycle signals
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Log task startup."""
    logger.info(f"Task {task.name} [{task_id}] starting")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, result=None, **kwargs):
    """Log successful task completion."""
    logger.info(f"Task {task.name} [{task_id}] completed successfully")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Log task failure."""
    logger.error(f"Task {sender.name} [{task_id}] failed: {str(exception)}")


__all__ = ["celery_app"]
