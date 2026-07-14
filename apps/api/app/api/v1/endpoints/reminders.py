from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentVault, DbSession
from app.core import audit
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.models import Document, Reminder, ReminderSend
from app.models.reminder import DEFAULT_LEAD_TIMES

router = APIRouter()

NEEDS_ATTENTION_DAYS = 30


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_date: date
    document_id: UUID | None = None
    lead_times: list[int] = Field(default_factory=lambda: list(DEFAULT_LEAD_TIMES), max_length=6)


class ReminderPatch(BaseModel):
    completed: bool


class ReminderOut(BaseModel):
    id: UUID
    title: str
    due_date: date
    channel: str
    lead_times: list[int]
    document_id: UUID | None
    document_title: str | None
    completed: bool
    created_at: datetime


class ReminderStats(BaseModel):
    total_active: int
    needs_attention: int  # due within 30 days — sidebar badge + dashboard KPI
    sent_total: int
    failed_total: int
    delivery_rate: float | None  # None until something has been sent


def _to_out(reminder: Reminder, document_title: str | None) -> ReminderOut:
    return ReminderOut(
        id=reminder.id,
        title=reminder.title,
        due_date=reminder.due_date,
        channel=reminder.channel,
        lead_times=reminder.lead_times,
        document_id=reminder.document_id,
        document_title=document_title,
        completed=reminder.completed_at is not None,
        created_at=reminder.created_at,
    )


@router.get("", response_model=list[ReminderOut])
async def list_reminders(db: DbSession, ctx: CurrentVault) -> list[ReminderOut]:
    rows = (
        await db.execute(
            select(Reminder, Document.title)
            .outerjoin(Document, Document.id == Reminder.document_id)
            .where(Reminder.vault_id == ctx.vault.id, Reminder.completed_at.is_(None))
            .order_by(Reminder.due_date)
            .limit(200)
        )
    ).all()
    return [_to_out(r, doc_title) for r, doc_title in rows]


@router.post("", response_model=ReminderOut, status_code=201)
async def create_reminder(body: ReminderCreate, db: DbSession, ctx: CurrentVault) -> ReminderOut:
    if not ctx.can_write:
        raise ForbiddenError("Your role cannot create reminders")
    document_title: str | None = None
    if body.document_id is not None:
        doc = await db.get(Document, body.document_id)
        if doc is None or doc.vault_id != ctx.vault.id:
            raise NotFoundError("Document not found")
        document_title = doc.title
    if any(lead < 0 or lead > 365 for lead in body.lead_times):
        raise AppError("Lead times must be between 0 and 365 days")

    reminder = Reminder(
        vault_id=ctx.vault.id,
        document_id=body.document_id,
        created_by=ctx.user.id,
        title=body.title,
        due_date=body.due_date,
        lead_times=sorted(set(body.lead_times), reverse=True),
    )
    db.add(reminder)
    await db.flush()
    await audit.record(
        db, "reminder.create", actor_id=ctx.user.id, entity_type="reminder", entity_id=reminder.id
    )
    await db.commit()
    return _to_out(reminder, document_title)


@router.patch("/{reminder_id}", response_model=ReminderOut)
async def patch_reminder(
    reminder_id: UUID, body: ReminderPatch, db: DbSession, ctx: CurrentVault
) -> ReminderOut:
    reminder = await db.get(Reminder, reminder_id)
    if reminder is None or reminder.vault_id != ctx.vault.id:
        raise NotFoundError("Reminder not found")
    reminder.completed_at = datetime.now(UTC) if body.completed else None
    await audit.record(
        db,
        "reminder.completed" if body.completed else "reminder.reopened",
        actor_id=ctx.user.id,
        entity_type="reminder",
        entity_id=reminder.id,
    )
    await db.commit()
    doc_title = None
    if reminder.document_id:
        doc = await db.get(Document, reminder.document_id)
        doc_title = doc.title if doc else None
    return _to_out(reminder, doc_title)


@router.delete("/{reminder_id}", status_code=204)
async def delete_reminder(reminder_id: UUID, db: DbSession, ctx: CurrentVault) -> None:
    reminder = await db.get(Reminder, reminder_id)
    if reminder is None or reminder.vault_id != ctx.vault.id:
        raise NotFoundError("Reminder not found")
    if not ctx.can_write:
        raise ForbiddenError("Your role cannot delete reminders")
    await db.delete(reminder)
    await audit.record(
        db, "reminder.delete", actor_id=ctx.user.id, entity_type="reminder", entity_id=reminder_id
    )
    await db.commit()


@router.get("/stats", response_model=ReminderStats)
async def reminder_stats(db: DbSession, ctx: CurrentVault) -> ReminderStats:
    today = date.today()
    active = select(Reminder).where(
        Reminder.vault_id == ctx.vault.id, Reminder.completed_at.is_(None)
    )
    total_active = (await db.scalar(select(func.count()).select_from(active.subquery()))) or 0
    needs_attention = (
        await db.scalar(
            select(func.count()).where(
                Reminder.vault_id == ctx.vault.id,
                Reminder.completed_at.is_(None),
                Reminder.due_date >= today,
                Reminder.due_date <= today + timedelta(days=NEEDS_ATTENTION_DAYS),
            )
        )
    ) or 0
    send_rows = (
        await db.execute(
            select(ReminderSend.status, func.count())
            .join(Reminder, Reminder.id == ReminderSend.reminder_id)
            .where(Reminder.vault_id == ctx.vault.id, ReminderSend.status.in_(["sent", "failed"]))
            .group_by(ReminderSend.status)
        )
    ).all()
    by_status: dict[str, int] = {status: count for status, count in send_rows}
    sent, failed = by_status.get("sent", 0), by_status.get("failed", 0)
    return ReminderStats(
        total_active=total_active,
        needs_attention=needs_attention,
        sent_total=sent,
        failed_total=failed,
        delivery_rate=round(sent / (sent + failed), 4) if (sent + failed) else None,
    )
