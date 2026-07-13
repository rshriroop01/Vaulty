from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "vaultly",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks.heartbeat", "app.worker.tasks.extraction"],
)

celery_app.conf.update(
    task_acks_late=True,  # re-deliver if a worker dies mid-task (99% reminder delivery target)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
)

# Beat schedule. The reminder scan (M5) will slot in here.
celery_app.conf.beat_schedule = {
    "heartbeat": {
        "task": "app.worker.tasks.heartbeat.heartbeat",
        "schedule": crontab(minute="0"),  # hourly
    },
}
