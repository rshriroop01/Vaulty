"""Stripe billing (M9): checkout, customer portal, and webhook verification.

Mirrors app/services/assistant.py: a Protocol wrapping the real SDK client,
injected behind a module-level factory (`get_billing`) so tests can supply a
fake and never hit the network or need real Stripe keys. `Vault.plan` is only
ever written from a verified webhook event (app/api/v1/endpoints/billing.py)
— never trusted from client input — so a client can't grant itself a plan by
calling /billing/checkout without actually paying.

Price ids identify what a customer bought; `price_for_plan`/`plan_for_price`
are the (settings-driven, pure) translation between a Stripe price id and our
own `VaultPlan` enum, kept here so both the checkout and webhook code paths
share one mapping.
"""

from typing import Any, Protocol, cast
from uuid import UUID

import stripe
import structlog

from app.core.config import get_settings
from app.models.vault import VaultPlan

logger = structlog.get_logger("billing")


class BillingProvider(Protocol):
    def create_checkout_session(
        self,
        *,
        customer_id: str | None,
        price_id: str,
        vault_id: UUID,
        success_url: str,
        cancel_url: str,
    ) -> str: ...

    def create_portal_session(self, *, customer_id: str, return_url: str) -> str: ...

    def verify_webhook(self, payload: bytes, sig_header: str) -> dict[str, Any]: ...


class StripeBilling:
    """Thin wrapper around the Stripe SDK. `create_checkout_session` stamps
    the price id into session metadata so the `checkout.session.completed`
    webhook can resolve the plan without a second (expand) API call."""

    def __init__(self) -> None:
        settings = get_settings()
        stripe.api_key = settings.stripe_secret_key
        self._webhook_secret = settings.stripe_webhook_secret

    def create_checkout_session(
        self,
        *,
        customer_id: str | None,
        price_id: str,
        vault_id: UUID,
        success_url: str,
        cancel_url: str,
    ) -> str:
        params: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "client_reference_id": str(vault_id),
            "metadata": {"price_id": price_id, "vault_id": str(vault_id)},
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if customer_id:
            params["customer"] = customer_id
        session = stripe.checkout.Session.create(**params)
        if not session.url:
            raise RuntimeError("Stripe returned no checkout URL")
        return session.url

    def create_portal_session(self, *, customer_id: str, return_url: str) -> str:
        session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        return session.url

    def verify_webhook(self, payload: bytes, sig_header: str) -> dict[str, Any]:
        event = stripe.Webhook.construct_event(  # type: ignore[no-untyped-call]
            payload, sig_header, self._webhook_secret
        )
        return cast(dict[str, Any], event)


def billing_enabled() -> bool:
    return bool(get_settings().stripe_secret_key)


def get_billing() -> BillingProvider:
    return StripeBilling()


def price_for_plan(plan: VaultPlan) -> str:
    """The Stripe price id to check out for a given paid plan. Raises for
    `free` (not purchasable) or an unconfigured price."""
    settings = get_settings()
    mapping = {
        VaultPlan.premium: settings.stripe_price_premium,
        VaultPlan.family: settings.stripe_price_family,
    }
    price = mapping.get(plan)
    if not price:
        raise ValueError(f"No Stripe price configured for the {plan.value} plan")
    return price


def plan_for_price(price_id: str) -> VaultPlan | None:
    """Reverse of `price_for_plan`. Returns None for an unrecognized/unconfigured
    price id — callers must treat that as "leave the plan alone", not an error,
    since we never want a webhook to accidentally downgrade/upgrade on a
    mapping miss."""
    if not price_id:
        return None
    settings = get_settings()
    if price_id == settings.stripe_price_family:
        return VaultPlan.family
    if price_id == settings.stripe_price_premium:
        return VaultPlan.premium
    return None
