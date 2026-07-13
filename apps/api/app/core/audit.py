from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def record(
    session: AsyncSession,
    action: str,
    *,
    actor_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    **context: Any,
) -> None:
    """Append an audit entry. Flushed with the caller's transaction — an action
    and its audit trail commit or roll back together."""
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            context=context,
        )
    )
