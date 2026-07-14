import asyncio

from app.worker.celery_app import celery_app


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.worker.tasks.reminders.scan_reminders",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def scan_reminders() -> dict[str, int]:
    from app.db.session import async_session_factory
    from app.services.email import get_email_provider
    from app.services.reminders import run_reminder_scan

    async def _run() -> dict[str, int]:
        async with async_session_factory() as db:
            return await run_reminder_scan(db, get_email_provider())

    return asyncio.run(_run())
