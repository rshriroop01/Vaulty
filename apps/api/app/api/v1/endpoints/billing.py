"""Billing & tiers (M9, PRD business model: Free / Premium $8.99 / Family
$14.99). Stripe is the source of truth for payment state; `Vault.plan` only
ever changes from a verified webhook event — checkout/portal endpoints just
redirect the owner to Stripe-hosted pages and never write the plan
themselves. Quotas (app/core/quotas.py) already react to `Vault.plan`
automatically, so this module is entirely about moving that one field.

Gates mirror the assistant (app/api/v1/endpoints/assistant.py): unconfigured
Stripe keys -> RFC 7807 503, not a 500. The webhook route is deliberately
excluded from the CurrentUser/CurrentVault dependencies — Stripe calls it
directly, and it authenticates via the signed payload instead of a session
cookie.
"""

import datetime as dt
from typing import Annotated, Any, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentVault, DbSession
from app.core import audit
from app.core.config import get_settings
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.quotas import PLAN_LIMITS
from app.models import (
    BillingCustomer,
    Document,
    DocumentStatus,
    StripeEvent,
    Vault,
    VaultMembership,
    VaultPlan,
    VaultRole,
)
from app.services.billing import (
    BillingProvider,
    billing_enabled,
    get_billing,
    plan_for_price,
    price_for_plan,
)

logger = structlog.get_logger("billing")

router = APIRouter()


class BillingUnavailableError(AppError):
    status_code = 503
    title = "Service Unavailable"


class BillingSummary(BaseModel):
    plan: str
    status: str | None
    member_count: int
    document_count: int
    storage_bytes: int
    document_limit: int | None
    storage_limit_bytes: int | None
    current_period_end: dt.datetime | None


class CheckoutRequest(BaseModel):
    plan: Literal["premium", "family"]


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


def _require_owner(ctx: CurrentVault) -> None:
    if ctx.role != VaultRole.owner:
        raise ForbiddenError("Only the vault owner can manage billing")


@router.get("/summary", response_model=BillingSummary)
async def summary(db: DbSession, ctx: CurrentVault) -> BillingSummary:
    """Current plan, subscription status, member count and usage-vs-limits —
    feeds the billing page's plan cards and usage line."""
    limits = PLAN_LIMITS[ctx.vault.plan]
    doc_count, used_bytes = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(Document.size_bytes), 0)).where(
                Document.vault_id == ctx.vault.id,
                Document.status != DocumentStatus.pending_upload,
            )
        )
    ).one()
    member_count = (
        await db.scalar(select(func.count()).where(VaultMembership.vault_id == ctx.vault.id))
    ) or 0
    customer = await db.scalar(
        select(BillingCustomer).where(BillingCustomer.vault_id == ctx.vault.id)
    )
    return BillingSummary(
        plan=ctx.vault.plan.value,
        status=customer.status if customer else None,
        member_count=member_count,
        document_count=doc_count,
        storage_bytes=used_bytes,
        document_limit=limits.max_documents,
        storage_limit_bytes=limits.max_storage_bytes,
        current_period_end=customer.current_period_end if customer else None,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    body: CheckoutRequest,
    db: DbSession,
    ctx: CurrentVault,
    billing: Annotated[BillingProvider, Depends(get_billing)],
) -> CheckoutResponse:
    if not billing_enabled():
        raise BillingUnavailableError("Billing is not configured")
    _require_owner(ctx)

    plan = VaultPlan(body.plan)
    try:
        price_id = price_for_plan(plan)
    except ValueError as exc:
        raise BillingUnavailableError(str(exc)) from exc

    # Reuse the existing Stripe customer if this vault has billed before, so
    # a second upgrade/downgrade attempt doesn't create a duplicate customer.
    existing = await db.scalar(
        select(BillingCustomer).where(BillingCustomer.vault_id == ctx.vault.id)
    )
    settings = get_settings()
    url = billing.create_checkout_session(
        customer_id=existing.stripe_customer_id if existing else None,
        price_id=price_id,
        vault_id=ctx.vault.id,
        success_url=f"{settings.frontend_url}/billing?checkout=success",
        cancel_url=f"{settings.frontend_url}/billing?checkout=cancel",
    )
    await audit.record(
        db,
        "billing.checkout_started",
        actor_id=ctx.user.id,
        entity_type="vault",
        entity_id=ctx.vault.id,
        plan=plan.value,
    )
    await db.commit()
    return CheckoutResponse(url=url)


@router.post("/portal", response_model=PortalResponse)
async def portal(
    db: DbSession,
    ctx: CurrentVault,
    billing: Annotated[BillingProvider, Depends(get_billing)],
) -> PortalResponse:
    if not billing_enabled():
        raise BillingUnavailableError("Billing is not configured")
    _require_owner(ctx)

    customer = await db.scalar(
        select(BillingCustomer).where(BillingCustomer.vault_id == ctx.vault.id)
    )
    if customer is None:
        raise NotFoundError("No billing account yet — upgrade a plan first")

    url = billing.create_portal_session(
        customer_id=customer.stripe_customer_id,
        return_url=f"{get_settings().frontend_url}/billing",
    )
    return PortalResponse(url=url)


# --- webhook -----------------------------------------------------------------
# Unauthenticated by design (no CurrentUser/CurrentVault dependency): Stripe
# is the caller, authenticated via the signed payload, not a session cookie.


async def _resolve_vault(db: AsyncSession, vault_id_raw: str | None) -> Vault | None:
    if not vault_id_raw:
        return None
    try:
        vault_id = UUID(vault_id_raw)
    except ValueError:
        return None
    return await db.get(Vault, vault_id)


async def _customer_for_stripe_id(
    db: AsyncSession, stripe_customer_id: str | None
) -> BillingCustomer | None:
    if not stripe_customer_id:
        return None
    customer = await db.scalar(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    )
    return customer


async def _handle_checkout_completed(db: AsyncSession, obj: dict[str, Any]) -> None:
    vault = await _resolve_vault(db, obj.get("client_reference_id"))
    if vault is None:
        logger.warning(
            "stripe_webhook_vault_not_found",
            client_reference_id=obj.get("client_reference_id"),
        )
        return

    stripe_customer_id = obj.get("customer")
    price_id = (obj.get("metadata") or {}).get("price_id", "")
    plan = plan_for_price(price_id)

    customer = await db.scalar(select(BillingCustomer).where(BillingCustomer.vault_id == vault.id))
    if customer is None:
        customer = BillingCustomer(vault_id=vault.id, stripe_customer_id=stripe_customer_id or "")
        db.add(customer)
    elif stripe_customer_id:
        customer.stripe_customer_id = stripe_customer_id
    customer.stripe_subscription_id = obj.get("subscription")
    customer.status = "active"

    if plan is not None:
        vault.plan = plan

    await audit.record(
        db,
        "billing.plan_changed",
        entity_type="vault",
        entity_id=vault.id,
        plan=vault.plan.value,
        status="active",
    )


async def _handle_subscription_updated(db: AsyncSession, obj: dict[str, Any]) -> None:
    customer = await _customer_for_stripe_id(db, obj.get("customer"))
    if customer is None:
        logger.warning("stripe_webhook_unknown_customer", customer_id=obj.get("customer"))
        return
    vault = await db.get(Vault, customer.vault_id)
    if vault is None:
        logger.warning("stripe_webhook_vault_missing", vault_id=str(customer.vault_id))
        return

    previous_status = customer.status
    status = obj.get("status", customer.status)
    customer.status = status

    period_end = obj.get("current_period_end")
    if period_end:
        customer.current_period_end = dt.datetime.fromtimestamp(period_end, tz=dt.UTC)

    items = ((obj.get("items") or {}).get("data")) or []
    price_id = (items[0].get("price") or {}).get("id", "") if items else ""
    plan = plan_for_price(price_id)

    if status == "active":
        if plan is not None:
            vault.plan = plan
        await audit.record(
            db,
            "billing.plan_changed",
            entity_type="vault",
            entity_id=vault.id,
            plan=vault.plan.value,
            status=status,
        )
    elif status == "past_due" and previous_status != "past_due":
        # Dunning window: Stripe retries the charge; the plan is kept as-is
        # until the subscription is actually canceled.
        await audit.record(
            db,
            "billing.payment_failed",
            entity_type="vault",
            entity_id=vault.id,
            plan=vault.plan.value,
            status=status,
        )


async def _handle_subscription_deleted(db: AsyncSession, obj: dict[str, Any]) -> None:
    customer = await _customer_for_stripe_id(db, obj.get("customer"))
    if customer is None:
        logger.warning("stripe_webhook_unknown_customer", customer_id=obj.get("customer"))
        return
    vault = await db.get(Vault, customer.vault_id)
    if vault is None:
        return

    vault.plan = VaultPlan.free
    customer.status = "canceled"
    await audit.record(
        db,
        "billing.plan_changed",
        entity_type="vault",
        entity_id=vault.id,
        plan=VaultPlan.free.value,
        status="canceled",
    )


_HANDLERS = {
    "checkout.session.completed": _handle_checkout_completed,
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_deleted,
}


@router.post("/webhook")
async def webhook(
    request: Request,
    db: DbSession,
    billing: Annotated[BillingProvider, Depends(get_billing)],
) -> dict[str, bool]:
    if not billing_enabled():
        raise BillingUnavailableError("Billing is not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = billing.verify_webhook(payload, sig_header)
    except Exception as exc:
        logger.warning("stripe_webhook_invalid_signature")
        raise AppError("Invalid webhook signature") from exc

    event_id = event.get("id")
    event_type = event.get("type", "")
    if not event_id:
        return {"received": True}

    # Idempotency ledger: insert the event id before processing. A conflict
    # means this delivery was already handled (Stripe retries) — 200, no-op.
    db.add(StripeEvent(id=event_id))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return {"received": True}

    handler = _HANDLERS.get(event_type)
    if handler is not None:
        obj = ((event.get("data") or {}).get("object")) or {}
        try:
            await handler(db, obj)
        except Exception as exc:
            # Roll back (releasing the event id from the ledger) and answer
            # non-2xx so Stripe actually redelivers; a 200 here would mark the
            # event consumed and silently drop the plan change.
            logger.exception("stripe_webhook_handler_failed", event_type=event_type)
            await db.rollback()
            raise BillingUnavailableError("Webhook processing failed — retry") from exc

    await db.commit()
    return {"received": True}
