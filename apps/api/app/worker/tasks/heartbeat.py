import structlog

from app.worker.celery_app import celery_app

logger = structlog.get_logger("worker")


@celery_app.task(name="app.worker.tasks.heartbeat.heartbeat")  # type: ignore[untyped-decorator]
def heartbeat() -> str:
    """Proves the worker + beat pipeline is alive end-to-end."""
    logger.info("heartbeat")
    return "ok"
