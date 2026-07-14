import re
from datetime import UTC, date, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentVault, DbSession, VaultContext
from app.core import audit
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.quotas import ALLOWED_CONTENT_TYPES, MAX_FILE_SIZE_BYTES, PLAN_LIMITS
from app.core.storage import StorageProvider, get_storage
from app.models import Document, DocumentCategory, DocumentStatus
from app.services.extraction import EXTRACTABLE_CONTENT_TYPES, extraction_enabled

logger = structlog.get_logger("documents")

router = APIRouter()

Storage = Annotated[StorageProvider, Depends(get_storage)]


class QuotaExceededError(AppError):
    status_code = 402
    title = "Quota Exceeded"


class UploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=300)
    content_type: str
    size_bytes: int = Field(gt=0)


class UploadTicket(BaseModel):
    document_id: UUID
    upload_url: str


class DocumentOut(BaseModel):
    id: UUID
    title: str
    file_name: str
    content_type: str
    size_bytes: int
    category: DocumentCategory
    status: DocumentStatus
    extracted: dict[str, Any] | None = None
    expiry_date: date | None = None
    created_at: datetime


class DownloadOut(BaseModel):
    url: str


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[-200:]


async def _get_owned(db: DbSession, ctx: CurrentVault, document_id: UUID) -> Document:
    doc = await db.get(Document, document_id)
    if doc is None or doc.vault_id != ctx.vault.id:
        raise NotFoundError("Document not found")
    return doc


@router.post("/uploads", response_model=UploadTicket, status_code=201)
async def initiate_upload(
    body: UploadRequest, db: DbSession, ctx: CurrentVault, storage: Storage
) -> UploadTicket:
    if not ctx.can_write:
        raise ForbiddenError("Your role cannot add documents")
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        raise AppError(f"Unsupported file type {body.content_type}. Use PDF, JPG, PNG or HEIC.")
    if body.size_bytes > MAX_FILE_SIZE_BYTES:
        raise AppError("File is larger than the 25 MB per-file limit.")

    limits = PLAN_LIMITS[ctx.vault.plan]
    doc_count, used_bytes = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(Document.size_bytes), 0)).where(
                Document.vault_id == ctx.vault.id
            )
        )
    ).one()
    if limits.max_documents is not None and doc_count >= limits.max_documents:
        raise QuotaExceededError(
            f"The free plan holds {limits.max_documents} documents. Upgrade for unlimited."
        )
    if limits.max_storage_bytes is not None and used_bytes + body.size_bytes > (
        limits.max_storage_bytes
    ):
        raise QuotaExceededError("This file would exceed the free plan's 100 MB storage limit.")

    from app.services.search import build_search_text

    doc_id = uuid4()
    title = body.file_name.rsplit(".", 1)[0][:300]
    doc = Document(
        id=doc_id,
        vault_id=ctx.vault.id,
        uploaded_by=ctx.user.id,
        title=title,
        search_text=build_search_text(title, body.file_name),
        file_name=body.file_name,
        file_key=f"{ctx.vault.id}/{doc_id}/{_safe_name(body.file_name)}",
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        status=DocumentStatus.pending_upload,
    )
    db.add(doc)
    await db.commit()

    url = await storage.presign_upload(doc.file_key, body.content_type)
    return UploadTicket(document_id=doc.id, upload_url=url)


def _enqueue_extraction(document_id: UUID) -> None:
    """Isolated so tests can monkeypatch; imports Celery lazily."""
    from app.worker.tasks.extraction import extract_document

    extract_document.delay(str(document_id))


async def _within_ocr_quota(db: DbSession, ctx: VaultContext) -> bool:
    limit = PLAN_LIMITS[ctx.vault.plan].ocr_per_month
    if limit is None:
        return True
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = (
        await db.scalar(
            select(func.count()).where(
                Document.vault_id == ctx.vault.id,
                Document.extraction_requested_at >= month_start,
            )
        )
    ) or 0
    return used < limit


@router.post("/{document_id}/complete", response_model=DocumentOut)
async def complete_upload(
    document_id: UUID, db: DbSession, ctx: CurrentVault, storage: Storage
) -> Document:
    doc = await _get_owned(db, ctx, document_id)
    if doc.status != DocumentStatus.pending_upload:
        return doc  # idempotent — retries are harmless
    actual_size = await storage.object_size(doc.file_key)
    if actual_size is None:
        raise AppError("Upload not found in storage — retry the upload.")
    doc.size_bytes = actual_size  # trust storage, not the client
    doc.status = DocumentStatus.uploaded
    await audit.record(
        db,
        "document.upload",
        actor_id=ctx.user.id,
        entity_type="document",
        entity_id=doc.id,
        file_name=doc.file_name,
        size_bytes=actual_size,
    )

    # M3: queue AI extraction when possible; otherwise the doc simply stays uploaded
    should_extract = (
        extraction_enabled()
        and doc.content_type in EXTRACTABLE_CONTENT_TYPES
        and await _within_ocr_quota(db, ctx)
    )
    if should_extract:
        doc.status = DocumentStatus.queued
        doc.extraction_requested_at = datetime.now(UTC)
    await db.commit()

    if should_extract:
        try:
            _enqueue_extraction(doc.id)
        except Exception:
            # Broker down must not fail the upload — revert to plain uploaded
            logger.exception("extraction_enqueue_failed", document_id=str(doc.id))
            doc.status = DocumentStatus.uploaded
            await db.commit()
    return doc


@router.get("", response_model=list[DocumentOut])
async def list_documents(db: DbSession, ctx: CurrentVault) -> list[Document]:
    rows = await db.scalars(
        select(Document)
        .where(
            Document.vault_id == ctx.vault.id,
            Document.status != DocumentStatus.pending_upload,
        )
        .order_by(Document.created_at.desc())
        .limit(200)
    )
    return list(rows)


@router.get("/{document_id}/download", response_model=DownloadOut)
async def download_document(
    document_id: UUID, db: DbSession, ctx: CurrentVault, storage: Storage
) -> DownloadOut:
    doc = await _get_owned(db, ctx, document_id)
    await audit.record(
        db, "document.download", actor_id=ctx.user.id, entity_type="document", entity_id=doc.id
    )
    await db.commit()
    return DownloadOut(url=await storage.presign_download(doc.file_key, doc.file_name))


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID, db: DbSession, ctx: CurrentVault, storage: Storage
) -> None:
    if not ctx.can_write:
        raise ForbiddenError("Your role cannot delete documents")
    doc = await _get_owned(db, ctx, document_id)
    await storage.delete_object(doc.file_key)
    await db.delete(doc)
    await audit.record(
        db,
        "document.delete",
        actor_id=ctx.user.id,
        entity_type="document",
        entity_id=doc.id,
        file_name=doc.file_name,
    )
    await db.commit()
