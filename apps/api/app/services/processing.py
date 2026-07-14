"""The M3 pipeline body: queued → processing → extracted | failed.

Lives in services (not the worker) so tests can drive it with fakes; the
Celery task is a thin wrapper around `process_document`.
"""

from uuid import UUID

import anyio.to_thread
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.storage import StorageProvider
from app.models import Document, DocumentCategory, DocumentStatus
from app.services.extraction import Extractor
from app.services.search import build_search_text

logger = structlog.get_logger("processing")


async def process_document(
    db: AsyncSession,
    storage: StorageProvider,
    extractor: Extractor,
    document_id: UUID,
) -> bool:
    """Returns True when extraction succeeded. Raises nothing — failures are
    recorded on the document so the UI can show a Failed state."""
    doc = await db.get(Document, document_id)
    if doc is None or doc.status != DocumentStatus.queued:
        logger.info("extraction_skipped", document_id=str(document_id))
        return False

    doc.status = DocumentStatus.processing
    await db.commit()

    try:
        file_bytes = await storage.get_object(doc.file_key)
        result = await anyio.to_thread.run_sync(
            extractor.extract, file_bytes, doc.content_type, doc.file_name
        )
        doc.category = DocumentCategory(result.category)
        doc.title = result.title[:300]
        doc.expiry_date = result.expiry_date
        doc.extracted = {
            "vendor": result.vendor,
            "document_date": result.document_date.isoformat() if result.document_date else None,
            "expiry_date": result.expiry_date.isoformat() if result.expiry_date else None,
            "amount": result.amount,
            "currency": result.currency,
            "fields": [{"label": f.label, "value": f.value} for f in result.fields],
        }
        doc.search_text = build_search_text(
            doc.title, doc.file_name, doc.extracted, doc.category.value
        )
        doc.status = DocumentStatus.extracted
        await audit.record(
            db,
            "document.extracted",
            entity_type="document",
            entity_id=doc.id,
            category=result.category,
        )
        await db.commit()
        return True
    except Exception:
        logger.exception("extraction_failed", document_id=str(document_id))
        await db.rollback()
        doc = await db.get(Document, document_id)
        if doc is not None:
            doc.status = DocumentStatus.failed
            await audit.record(
                db, "document.extraction_failed", entity_type="document", entity_id=doc.id
            )
            await db.commit()
        return False
