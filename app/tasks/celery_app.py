# app/tasks/celery_app.py
from celery import Celery
from ..config import settings

celery_app = Celery(
    "app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-scheduled-posts": {
            "task": "app.tasks.scheduled_tasks.check_scheduled_posts",
            "schedule": 60.0,  # Run every minute
        },
    },
)