# app/celery_app.py
from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Celery
celery_app = Celery(
    'social_media_manager',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['app.tasks.scheduled_tasks']  # Import tasks module
)

# Celery Configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Periodic Tasks Schedule
celery_app.conf.beat_schedule = {
    'check-scheduled-posts-every-minute': {
        'task': 'app.tasks.scheduled_tasks.check_scheduled_posts',
        'schedule': crontab(minute='*'),  # Every minute
    },
}

if __name__ == '__main__':
    celery_app.start()