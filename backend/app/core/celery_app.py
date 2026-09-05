"""
Celery Configuration with Redis Broker
======================================
Sets up the Celery application using Redis as both message broker and result backend.
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "compliance_scanner",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.scan_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,       # 1 hour max task time
    result_expires=86400,        # 24 hours result expiration
    broker_connection_retry_on_startup=False,
    broker_connection_max_retries=0,
    result_backend_transport_options={
        "max_retries": 0,
        "interval_start": 0,
        "interval_step": 0,
        "interval_max": 0,
    },
)
