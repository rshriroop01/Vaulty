"""AI assistant (M8, screen 2c "VAULTLY ANSWER" card): Q&A over the vault's
own documents, retrieved via the M4 search service and answered by Claude.

Gates, in order: feature flag → plan → API key configured. The Claude call is
sync (see app/services/assistant.py, mirrors extraction), so it's run off the
event loop via anyio.to_thread.run_sync — the same pattern used for storage
signing and outbound email.
"""

import time
from typing import Annotated

import anyio.to_thread
import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentVault, DbSession
from app.core import audit
from app.core.errors import AppError, ForbiddenError
from app.core.feature_flags import is_enabled
from app.models import VaultPlan
from app.services.assistant import (
    AssistantProvider,
    RetrievalProvider,
    SuggestedAction,
    apply_guardrails,
    assistant_enabled,
    get_assistant,
    get_retrieval,
)

logger = structlog.get_logger("assistant")

router = APIRouter()

FLAG_KEY = "assistant"


class AssistantDisabledError(ForbiddenError):
    pass


class PlanUpgradeRequiredError(AppError):
    status_code = 403
    title = "Upgrade Required"
    error_type = "https://vaultly.app/problems/plan-upgrade-required"


class AssistantUnavailableError(AppError):
    status_code = 503
    title = "Service Unavailable"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class CitationOut(BaseModel):
    document_id: str
    title: str
    category: str


class AskResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    suggested_actions: list[SuggestedAction]
    retrieved_count: int
    latency_ms: int


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    db: DbSession,
    ctx: CurrentVault,
    retrieval: Annotated[RetrievalProvider, Depends(get_retrieval)],
    assistant: Annotated[AssistantProvider, Depends(get_assistant)],
) -> AskResponse:
    started = time.perf_counter()

    if not await is_enabled(db, FLAG_KEY, default=False):
        raise AssistantDisabledError("Assistant is not enabled")
    if ctx.vault.plan == VaultPlan.free:
        raise PlanUpgradeRequiredError(
            "The Vaultly assistant is a Premium feature — upgrade to ask questions "
            "across your vault."
        )
    if not assistant_enabled():
        raise AssistantUnavailableError("Assistant unavailable")

    documents = await retrieval.retrieve(db, ctx, body.question, limit=8)
    raw_answer = await anyio.to_thread.run_sync(assistant.ask, body.question, documents)

    retrieved_ids = {str(d.id) for d in documents}
    answer = apply_guardrails(raw_answer, retrieved_ids)

    docs_by_id = {str(d.id): d for d in documents}
    citations = [
        CitationOut(
            document_id=cid,
            title=docs_by_id[cid].title,
            category=docs_by_id[cid].category.value,
        )
        for cid in answer.citations
        if cid in docs_by_id
    ]

    latency_ms = int((time.perf_counter() - started) * 1000)
    await audit.record(
        db,
        "assistant.ask",
        actor_id=ctx.user.id,
        entity_type="vault",
        entity_id=ctx.vault.id,
        question_length=len(body.question),
        retrieved_count=len(documents),
    )
    await db.commit()

    logger.info(
        "assistant_ask",
        retrieved_count=len(documents),
        citations=len(citations),
        latency_ms=latency_ms,
    )
    return AskResponse(
        answer=answer.answer,
        citations=citations,
        suggested_actions=answer.suggested_actions,
        retrieved_count=len(documents),
        latency_ms=latency_ms,
    )
