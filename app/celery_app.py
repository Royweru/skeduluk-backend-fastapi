# app/celery_app.py
from celery import Celery
import os
import ssl

# Get Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Configure broker and backend URLs with SSL parameters
def configure_redis_url(url: str) -> dict:
    """Configure Redis connection with SSL support for Upstash"""
    if url.startswith('rediss://'):
        # Return configuration dict with SSL settings
        return {
            'url': url,
            'ssl': {
                'ssl_cert_reqs': ssl.CERT_NONE,
            }
        }
    return {'url': url}

# Initialize Celery
celery_app = Celery(
    "social_scheduler",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Configure Celery with SSL support
celery_app.conf.update(
    # Task settings
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
    
    # SSL Configuration for broker and backend
    broker_use_ssl={
        'ssl_cert_reqs': ssl.CERT_NONE,
        'ssl_ca_certs': None,
        'ssl_certfile': None,
        'ssl_keyfile': None,
    },
    redis_backend_use_ssl={
        'ssl_cert_reqs': ssl.CERT_NONE,
        'ssl_ca_certs': None,
        'ssl_certfile': None,
        'ssl_keyfile': None,
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(['app.tasks'])