"""The reminder scan (M5): for every active reminder, send the most imminent
pending lead-time email, exactly once per (reminder, lead time).

Sits in services so tests drive it with fakes and a pinned `today`; the beat
task is a thin wrapper. Delivery outcomes land in `reminder_sends` — the data
behind the 99% delivery target (PRD) and the 2e delivery-rate card.
"""

from datetime import date, timedelta

import anyio.to_thread
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.models import Reminder, ReminderSend, User
from app.services.email import EmailProvider

logger = structlog.get_logger("reminders")


def _subject(reminder: Reminder, today: date) -> str:
    days_left = (reminder.due_date - today).days
    when = "today" if days_left <= 0 else f"in {days_left} day{'s' if days_left != 1 else ''}"
    return f"Vaultly reminder: {reminder.title} — {when}"


def _body(reminder: Reminder, today: date) -> str:
    return (
        f"{reminder.title}\n"
        f"Due: {reminder.due_date.isoformat()}\n\n"
        f"Open Vaultly to review the linked document or snooze this reminder.\n"
        f"— Vaultly · never miss an important deadline"
    )


async def run_reminder_scan(
    db: AsyncSession, email: EmailProvider, today: date | None = None
) -> dict[str, int]:
    today = today or date.today()
    reminders = (
        await db.scalars(
            select(Reminder).where(Reminder.completed_at.is_(None), Reminder.due_date >= today)
        )
    ).all()

    stats = {"sent": 0, "failed": 0, "skipped": 0}
    for reminder in reminders:
        handled = set(
            (
                await db.scalars(
                    select(ReminderSend.lead_days).where(ReminderSend.reminder_id == reminder.id)
                )
            ).all()
        )
        due_leads = sorted(
            lead
            for lead in reminder.lead_times
            if lead not in handled and reminder.due_date - timedelta(days=lead) <= today
        )
        if not due_leads:
            continue

        # Send only the most imminent pending lead; retire the staler ones so a
        # reminder created late doesn't fire three emails at once.
        send_lead = due_leads[0]
        for stale_lead in due_leads[1:]:
            db.add(ReminderSend(reminder_id=reminder.id, lead_days=stale_lead, status="skipped"))
            stats["skipped"] += 1

        recipient = await db.get(User, reminder.created_by)
        try:
            if recipient is None:
                raise RuntimeError("reminder creator no longer exists")
            subject, body = _subject(reminder, today), _body(reminder, today)
            await anyio.to_thread.run_sync(email.send, recipient.email, subject, body)
            db.add(ReminderSend(reminder_id=reminder.id, lead_days=send_lead, status="sent"))
            await audit.record(
                db,
                "reminder.sent",
                entity_type="reminder",
                entity_id=reminder.id,
                lead_days=send_lead,
            )
            stats["sent"] += 1
        except Exception as exc:
            logger.exception("reminder_send_failed", reminder_id=str(reminder.id))
            db.add(
                ReminderSend(
                    reminder_id=reminder.id,
                    lead_days=send_lead,
                    status="failed",
                    error=str(exc)[:500],
                )
            )
            stats["failed"] += 1
        await db.commit()

    logger.info("reminder_scan", **stats, active=len(reminders))
    return stats
