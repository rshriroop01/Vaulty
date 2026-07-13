import asyncio
from uuid import UUID

from app.worker.celery_app import celery_app


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.worker.tasks.extraction.extract_document",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def extract_document(document_id: str) -> bool:
    from app.core.storage import get_storage
    from app.db.session import async_session_factory
    from app.services.extraction import get_extractor
    from app.services.processing import process_document

    async def _run() -> bool:
        async with async_session_factory() as db:
            return await process_document(db, get_storage(), get_extractor(), UUID(document_id))

    return asyncio.run(_run())
