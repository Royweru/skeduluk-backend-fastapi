# app/celery_app.py
from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv
import ssl  # <--- IMPORT SSL

load_dotenv()

# Initialize Celery
celery_app = Celery(
    'social_media_manager',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['app.tasks.scheduled_tasks']
)

# Celery Configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# --- ADD THIS BLOCK TO FIX SSL ---
broker_url = os.getenv('CELERY_BROKER_URL', '')
if broker_url.startswith('rediss://'):
    celery_app.conf.broker_transport_options = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    celery_app.conf.redis_backend_transport_options = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
# --- END OF FIX ---


# Periodic Tasks Schedule
celery_app.conf.beat_schedule = {
    'check-scheduled-posts-every-minute': {
        'task': 'app.tasks.scheduled_tasks.check_scheduled_posts',
        'schedule': crontab(minute='*'),
    },
}

if __name__ == '__main__':
    celery_app.start()