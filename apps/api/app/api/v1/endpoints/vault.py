from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentVault, DbSession
from app.core.quotas import PLAN_LIMITS
from app.models import Document, DocumentCategory, DocumentStatus, VaultMembership

router = APIRouter()


class VaultUsage(BaseModel):
    vault_id: UUID
    plan: str
    document_count: int
    storage_bytes: int
    document_limit: int | None
    storage_limit_bytes: int | None
    member_count: int
    categories: dict[str, int]


@router.get("/usage", response_model=VaultUsage)
async def vault_usage(db: DbSession, ctx: CurrentVault) -> VaultUsage:
    """Feeds the sidebar storage meter, dashboard KPIs, and category grid."""
    doc_count, used_bytes = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(Document.size_bytes), 0)).where(
                Document.vault_id == ctx.vault.id,
                Document.status != DocumentStatus.pending_upload,
            )
        )
    ).one()
    member_count = (
        await db.scalar(select(func.count()).where(VaultMembership.vault_id == ctx.vault.id))
    ) or 0
    category_rows = (
        await db.execute(
            select(Document.category, func.count())
            .where(
                Document.vault_id == ctx.vault.id,
                Document.status != DocumentStatus.pending_upload,
            )
            .group_by(Document.category)
        )
    ).all()
    by_category: dict[DocumentCategory, int] = {cat: count for cat, count in category_rows}
    limits = PLAN_LIMITS[ctx.vault.plan]
    return VaultUsage(
        vault_id=ctx.vault.id,
        plan=ctx.vault.plan.value,
        document_count=doc_count,
        storage_bytes=used_bytes,
        document_limit=limits.max_documents,
        storage_limit_bytes=limits.max_storage_bytes,
        member_count=member_count,
        categories={c.value: by_category.get(c, 0) for c in DocumentCategory},
    )
