from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import CurrentVault, DbSession
from app.models import DocumentCategory
from app.services.search import search_documents

router = APIRouter()


class SearchResult(BaseModel):
    id: UUID
    title: str
    file_name: str
    category: DocumentCategory
    status: str
    size_bytes: int
    snippet: str
    score: float
    expiry_date: date | None
    extracted: dict[str, Any] | None
    created_at: datetime


class SearchResponse(BaseModel):
    query: str
    latency_ms: int
    total: int
    counts: dict[str, int]
    results: list[SearchResult]


@router.get("", response_model=SearchResponse)
async def search(
    db: DbSession,
    ctx: CurrentVault,
    q: str = Query(min_length=1, max_length=200),
    category: DocumentCategory | None = None,
) -> SearchResponse:
    outcome = await search_documents(
        db,
        ctx.vault.id,
        q,
        category.value if category else None,
        visible_categories=ctx.visible_categories(),
    )
    return SearchResponse(
        query=q,
        latency_ms=outcome.latency_ms,
        total=sum(outcome.counts.values()),
        counts=outcome.counts,
        results=[
            SearchResult(
                id=hit.document.id,
                title=hit.document.title,
                file_name=hit.document.file_name,
                category=hit.document.category,
                status=hit.document.status.value,
                size_bytes=hit.document.size_bytes,
                snippet=hit.snippet,
                score=round(hit.score, 2),
                expiry_date=hit.document.expiry_date,
                extracted=hit.document.extracted,
                created_at=hit.document.created_at,
            )
            for hit in outcome.hits
        ],
    )
