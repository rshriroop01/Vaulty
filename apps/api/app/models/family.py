from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.audit import PortableJSON


class VaultInvite(Base, TimestampMixin):
    """Email invitation to join a vault. The raw token lives only in the email
    link; we store its hash."""

    __tablename__ = "vault_invites"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    vault_id: Mapped[UUID] = mapped_column(ForeignKey("vaults.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # admin | member | emergency
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invited_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmergencyBinder(Base, TimestampMixin):
    """One per vault: the curated crisis packet (screen 2h). Documents are NOT
    duplicated here — insurance/ID presence is derived from the vault."""

    __tablename__ = "emergency_binders"

    vault_id: Mapped[UUID] = mapped_column(
        ForeignKey("vaults.id", ondelete="CASCADE"), primary_key=True
    )
    # [{name, phone, relation}]
    contacts: Mapped[list[dict[str, Any]]] = mapped_column(PortableJSON, default=list)
    # {blood_group, allergies, medications, hospital, notes}
    medical: Mapped[dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    # [{name, relation}] — who has been handed the QR/PIN
    delegates: Mapped[list[dict[str, Any]]] = mapped_column(PortableJSON, default=list)


class EmergencyToken(Base):
    """Signed, revocable QR access token. PIN is argon2-hashed; raw token is
    returned exactly once at issue time (it lives inside the printed QR)."""

    __tablename__ = "emergency_tokens"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    vault_id: Mapped[UUID] = mapped_column(ForeignKey("vaults.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    pin_hash: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
