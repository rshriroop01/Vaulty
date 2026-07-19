"""Vault Q&A via Claude (M8, screen 2c "VAULTLY ANSWER" card).

Mirrors app/services/extraction.py: a sync provider class wrapping the
Anthropic client with `messages.parse` structured outputs, injected behind a
Protocol so tests can supply a fake and never hit the network.

Retrieval reuses the M4 FTS search service and is ALWAYS scoped to the caller's
vault (`ctx.vault.id`) and the M7 category-access matrix
(`ctx.visible_categories()`) — there must be no code path here that reads
documents without that filter. The model's own citations/actions are never
trusted either: `apply_guardrails` strips any document id the retrieval step
didn't hand it before the response leaves this module.
"""

import datetime as dt
from typing import Literal, Protocol

import anthropic
import structlog
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import VaultContext
from app.core.config import get_settings
from app.models import Document
from app.services.search import search_documents

logger = structlog.get_logger("assistant")

DEFAULT_RETRIEVAL_LIMIT = 8

SYSTEM_PROMPT = """You are the Vaultly assistant. Vaultly is a vault for household \
documents: receipts, warranties, insurance policies, medical bills, IDs and legal papers, \
and home documents. Answer the user's question using ONLY the document summaries provided \
below — never invent facts, dates, or amounts. If the documents don't contain the answer, \
say so plainly instead of guessing. Every factual claim must cite the id(s) of the \
document(s) it came from in `citations`. When the question involves an upcoming date \
(a renewal, expiry, due date, or deadline), suggest a `create_reminder` action for the \
relevant document with that date; suggest `open_document` when a document is directly \
relevant but no date action applies."""


class SuggestedAction(BaseModel):
    type: Literal["create_reminder", "open_document"]
    document_id: str
    label: str
    date: dt.date | None = None


class AssistantAnswer(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)


class RetrievalProvider(Protocol):
    async def retrieve(
        self, session: AsyncSession, ctx: VaultContext, query: str, limit: int
    ) -> list[Document]: ...


class FtsRetrieval:
    """Reuses the M4 search service. Always filtered by vault + visible categories —
    the tenant-isolation guardrail for the assistant's document access."""

    async def retrieve(
        self, session: AsyncSession, ctx: VaultContext, query: str, limit: int
    ) -> list[Document]:
        outcome = await search_documents(
            session,
            ctx.vault.id,
            query,
            visible_categories=ctx.visible_categories(),
        )
        return [hit.document for hit in outcome.hits[:limit]]


def _serialize_document(doc: Document) -> str:
    """Metadata-only block — never file bytes. Keeps the prompt small and avoids
    resending already-extracted content back through the model as raw files."""
    extracted = doc.extracted or {}
    expiry = doc.expiry_date.isoformat() if doc.expiry_date else extracted.get("expiry_date")
    amount = extracted.get("amount")
    amount_str = f"{amount if amount is not None else '—'} {extracted.get('currency') or ''}"
    lines = [
        f"id: {doc.id}",
        f"title: {doc.title}",
        f"category: {doc.category.value}",
        f"vendor: {extracted.get('vendor') or '—'}",
        f"document_date: {extracted.get('document_date') or '—'}",
        f"expiry_date: {expiry or '—'}",
        f"amount: {amount_str.strip()}",
    ]
    for field in extracted.get("fields", []) or []:
        lines.append(f"field {field.get('label', '')}: {field.get('value', '')}")
    return "\n".join(lines)


def build_prompt(question: str, documents: list[Document]) -> str:
    if not documents:
        blocks = "(no documents matched this question)"
    else:
        blocks = "\n\n".join(
            f"Document {i + 1}:\n{_serialize_document(d)}" for i, d in enumerate(documents)
        )
    return f"Documents:\n{blocks}\n\nQuestion: {question}"


class AssistantProvider(Protocol):
    def ask(self, question: str, documents: list[Document]) -> AssistantAnswer: ...


class ClaudeAssistant:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.assistant_model

    def ask(self, question: str, documents: list[Document]) -> AssistantAnswer:
        prompt = build_prompt(question, documents)
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_format=AssistantAnswer,
        )
        result = response.parsed_output
        if result is None:
            raise RuntimeError("Assistant returned no parseable output")
        logger.info("assistant_answered", documents=len(documents), model=self._model)
        return result


def apply_guardrails(answer: AssistantAnswer, retrieved_ids: set[str]) -> AssistantAnswer:
    """Pure post-filter: drop any citation or suggested action whose document_id
    was not in the retrieved set. The model's output is never trusted as-is —
    this is the last line of defense against a hallucinated or cross-tenant id."""
    return answer.model_copy(
        update={
            "citations": [c for c in answer.citations if c in retrieved_ids],
            "suggested_actions": [
                a for a in answer.suggested_actions if a.document_id in retrieved_ids
            ],
        }
    )


def assistant_enabled() -> bool:
    return bool(get_settings().anthropic_api_key)


def get_retrieval() -> RetrievalProvider:
    return FtsRetrieval()


def get_assistant() -> AssistantProvider:
    return ClaudeAssistant()
