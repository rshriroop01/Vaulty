from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class BillingCustomer(Base, TimestampMixin):
    """Links a vault to its Stripe customer/subscription (M9). One per vault —
    the vault, not the user, is the billing unit (ARCHITECTURE.md #3)."""

    __tablename__ = "billing_customers"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    vault_id: Mapped[UUID] = mapped_column(
        ForeignKey("vaults.id", ondelete="CASCADE"), unique=True, index=True
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(255), index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # active | past_due | canceled | ... (mirrors Stripe subscription status)
    status: Mapped[str] = mapped_column(String(20), default="active")
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class StripeEvent(Base):
    """Webhook idempotency ledger: Stripe retries deliveries, so every event id
    is recorded before it's processed. A conflict on insert means "already
    handled" — the webhook returns 200 without reprocessing."""

    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
