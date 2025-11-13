# app/celery_app.py
from celery import Celery
import os
import ssl

# Get Redis URL from environment, default to local Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize Celery
celery_app = Celery(
    "social_scheduler",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Base Celery configuration
celery_config = {
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'UTC',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': 30 * 60,
    'task_soft_time_limit': 25 * 60,
    'worker_prefetch_multiplier': 1,
    'worker_max_tasks_per_child': 1000,
    'beat_schedule': {
        'check-scheduled-posts-every-minute': {
            'task': 'app.tasks.scheduled_tasks.check_scheduled_posts',
            'schedule': 60.0,  # Run every 60 seconds
        },
    },
}

# Add SSL options only if using a 'rediss://' URL (like for Upstash)
if REDIS_URL.startswith('rediss://'):
    print("✅ Configuring Celery with SSL for Redis.")
    ssl_options = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    celery_config['broker_use_ssl'] = ssl_options
    celery_config['redis_backend_use_ssl'] = ssl_options
else:
    print("ℹ️  Configuring Celery without SSL for Redis.")

# Update Celery app with the final configuration
celery_app.conf.update(celery_config)

# Add 'imports' to ensure tasks are discovered
celery_app.conf.imports = ('app.tasks.scheduled_tasks',)