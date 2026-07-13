from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# JSONB on Postgres, plain JSON elsewhere (in-memory SQLite in tests)
PortableJSON = JSON().with_variant(JSONB(), "postgresql")


class AuditLog(Base):
    """Append-only record of every security-relevant action.

    Required by the PRD ("comprehensive audit logging") and load-bearing for
    emergency access, family sharing, and document lifecycle events.
    """

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)  # null = system action
    action: Mapped[str] = mapped_column(String(100))  # e.g. "document.upload", "emergency.scan"
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    context: Mapped[dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
