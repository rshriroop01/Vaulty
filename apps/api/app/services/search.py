"""Vault search (M4, screen 2c).

Postgres path: full-text search with prefix matching (`to_tsquery` with `:*`)
ranked by `ts_rank`, plus an ILIKE net for mid-word fragments. The GIN index
from migration 0005 keeps this comfortably under the PRD's 300ms target.
Other dialects (SQLite in tests): plain ILIKE with a title-boost heuristic —
same contract, portable behavior.
"""

import re
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentStatus

logger = structlog.get_logger("search")

SNIPPET_WINDOW = 70
MAX_RESULTS = 30


def build_search_text(
    title: str,
    file_name: str,
    extracted: dict[str, Any] | None = None,
    category: str | None = None,
) -> str:
    """Flatten everything findable about a document into one indexed string."""
    parts: list[str] = [title, file_name]
    if category:
        parts.append(category.replace("_", " "))
    if extracted:
        for key in ("vendor", "document_date", "expiry_date", "currency"):
            if extracted.get(key):
                parts.append(str(extracted[key]))
        if extracted.get("amount") is not None:
            parts.append(str(extracted["amount"]))
        for field in extracted.get("fields", []):
            parts.append(f"{field.get('label', '')} {field.get('value', '')}")
    return " ".join(p for p in parts if p).strip()


def _terms(q: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z0-9]+", q) if t][:8]


def make_snippet(search_text: str, q: str) -> str:
    """Window of the indexed text around the first query-term hit."""
    lowered = search_text.lower()
    pos = -1
    for term in _terms(q):
        pos = lowered.find(term.lower())
        if pos != -1:
            break
    if pos == -1:
        return search_text[: SNIPPET_WINDOW * 2].strip()
    start = max(0, pos - SNIPPET_WINDOW)
    end = min(len(search_text), pos + SNIPPET_WINDOW)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(search_text) else ""
    return f"{prefix}{search_text[start:end].strip()}{suffix}"


@dataclass
class SearchHit:
    document: Document
    score: float
    snippet: str


@dataclass
class SearchOutcome:
    hits: list[SearchHit]
    counts: dict[str, int]  # matches per category, pre-filter (for the chips)
    latency_ms: int


async def search_documents(
    db: AsyncSession,
    vault_id: UUID,
    q: str,
    category: str | None = None,
    visible_categories: list[str] | None = None,
) -> SearchOutcome:
    started = time.perf_counter()
    terms = _terms(q)
    if not terms:
        return SearchOutcome(hits=[], counts={}, latency_ms=0)

    base_filter = [
        Document.vault_id == vault_id,
        Document.status != DocumentStatus.pending_upload,
    ]
    if visible_categories is not None:
        base_filter.append(Document.category.in_(visible_categories))
    ilike_any = or_(*[Document.search_text.ilike(f"%{t}%") for t in terms])

    if db.get_bind().dialect.name == "postgresql":
        tsvector = func.to_tsvector("english", Document.search_text)
        # Prefix-match every term: "samsu wash" → samsu:* & wash:*
        tsquery = func.to_tsquery("english", " & ".join(f"{t}:*" for t in terms))
        rank = func.ts_rank(tsvector, tsquery).label("score")
        stmt = select(Document, rank).where(
            *base_filter, or_(tsvector.op("@@")(tsquery), ilike_any)
        )
        rows = (await db.execute(stmt)).all()
        # An ILIKE-only hit (mid-word fragment) ranks 0 — keep it, just low
        scored = [(doc, max(float(raw or 0.0), 0.05)) for doc, raw in rows]
    else:
        stmt = select(Document).where(*base_filter, ilike_any)
        docs = (await db.scalars(stmt)).all()
        scored = []
        for doc in docs:
            title_hits = sum(1 for t in terms if t.lower() in doc.title.lower())
            scored.append((doc, 0.3 + 0.2 * title_hits))

    scored = [(d, min(s, 0.99)) for d, s in scored]
    scored.sort(key=lambda pair: (pair[1], pair[0].created_at), reverse=True)

    counts: dict[str, int] = {}
    for doc, _ in scored:
        counts[doc.category.value] = counts.get(doc.category.value, 0) + 1

    if category:
        scored = [(d, s) for d, s in scored if d.category.value == category]
    scored = scored[:MAX_RESULTS]

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info("search", terms=len(terms), results=len(scored), latency_ms=latency_ms)
    return SearchOutcome(
        hits=[
            SearchHit(document=d, score=s, snippet=make_snippet(d.search_text, q))
            for d, s in scored
        ],
        counts=counts,
        latency_ms=latency_ms,
    )
