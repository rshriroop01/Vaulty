from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.audit import PortableJSON

DEFAULT_LEAD_TIMES = [30, 7, 1]  # days before due — the 2e chips


class Reminder(Base, TimestampMixin):
    __tablename__ = "reminders"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    vault_id: Mapped[UUID] = mapped_column(ForeignKey("vaults.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(300))
    due_date: Mapped[date] = mapped_column(Date, index=True)
    channel: Mapped[str] = mapped_column(String(20), default="email")
    lead_times: Mapped[list[int]] = mapped_column(
        PortableJSON, default=lambda: list(DEFAULT_LEAD_TIMES)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReminderSend(Base):
    """One row per (reminder, lead time) the scan has handled — the idempotency
    key and the data behind the 99% delivery-rate metric (screen 2e)."""

    __tablename__ = "reminder_sends"
    __table_args__ = (UniqueConstraint("reminder_id", "lead_days"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    reminder_id: Mapped[UUID] = mapped_column(
        ForeignKey("reminders.id", ondelete="CASCADE"), index=True
    )
    lead_days: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20))  # sent | failed | skipped
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
