"""M9 billing & tiers: checkout/portal gating, webhook idempotency and event
handling, and the exit criterion (family plan -> pay -> add 6 members).

A fake BillingProvider is injected everywhere (mirrors tests/test_assistant.py's
FakeAssistant) — no test in this file touches the real Stripe SDK or network.
Signature verification, checkout-session creation, and portal-session creation
are all owned by the fake, so `stripe_secret_key`/`stripe_webhook_secret` stay
empty exactly as they are in every other test environment.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.v1.endpoints.billing as billing_endpoint
from app.models import AuditLog, BillingCustomer, Vault, VaultPlan
from app.services.billing import get_billing
from tests.test_documents import SIGNUP, FakeStorage
from tests.test_family import CapturingEmail, _invite_and_join, _invite_token, emails

__all__ = ["emails"]  # re-exported fixture; keeps linters from flagging the unused import

FAKE_PREMIUM_PRICE = "price_premium_test"
FAKE_FAMILY_PRICE = "price_family_test"


async def _session(app: FastAPI) -> AsyncSession:
    from app.db.session import get_db_session

    factory = app.dependency_overrides[get_db_session]
    return await factory().__anext__()  # type: ignore[no-any-return]


def _fake_price_for_plan(plan: VaultPlan) -> str:
    return {VaultPlan.premium: FAKE_PREMIUM_PRICE, VaultPlan.family: FAKE_FAMILY_PRICE}[plan]


def _fake_plan_for_price(price_id: str) -> VaultPlan | None:
    return {FAKE_PREMIUM_PRICE: VaultPlan.premium, FAKE_FAMILY_PRICE: VaultPlan.family}.get(
        price_id
    )


@pytest.fixture
def billing_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real gate checks STRIPE_SECRET_KEY (empty in test env); tests that
    need to reach checkout/portal/webhook flip it on and swap in a fake
    price<->plan mapping, mirroring test_assistant.py's api_key_configured."""
    monkeypatch.setattr(billing_endpoint, "billing_enabled", lambda: True)
    monkeypatch.setattr(billing_endpoint, "price_for_plan", _fake_price_for_plan)
    monkeypatch.setattr(billing_endpoint, "plan_for_price", _fake_plan_for_price)


class FakeBilling:
    def __init__(self) -> None:
        self.checkout_calls: list[dict[str, Any]] = []
        self.portal_calls: list[dict[str, Any]] = []
        self.checkout_url = "https://checkout.stripe.test/session/test"
        self.portal_url = "https://billing.stripe.test/portal/test"
        self.event: dict[str, Any] | None = None
        self.raise_on_verify = False

    def create_checkout_session(
        self,
        *,
        customer_id: str | None,
        price_id: str,
        vault_id: UUID,
        success_url: str,
        cancel_url: str,
    ) -> str:
        self.checkout_calls.append(
            {
                "customer_id": customer_id,
                "price_id": price_id,
                "vault_id": vault_id,
                "success_url": success_url,
                "cancel_url": cancel_url,
            }
        )
        return self.checkout_url

    def create_portal_session(self, *, customer_id: str, return_url: str) -> str:
        self.portal_calls.append({"customer_id": customer_id, "return_url": return_url})
        return self.portal_url

    def verify_webhook(self, payload: bytes, sig_header: str) -> dict[str, Any]:
        if self.raise_on_verify:
            raise ValueError("invalid signature")
        assert self.event is not None, "test must set fake.event before posting the webhook"
        return self.event


def _override_billing(app: FastAPI, fake: FakeBilling) -> None:
    app.dependency_overrides[get_billing] = lambda: fake


def _event(event_id: str, event_type: str, obj: dict[str, Any]) -> dict[str, Any]:
    return {"id": event_id, "type": event_type, "data": {"object": obj}}


async def _post_webhook(client: AsyncClient) -> Any:
    return await client.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=fake", "Content-Type": "application/json"},
    )


async def _new_client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def storage(app: FastAPI) -> FakeStorage:
    from app.core.storage import get_storage

    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


@pytest.fixture
async def authed(client: AsyncClient, storage: FakeStorage) -> AsyncClient:
    resp = await client.post("/api/v1/auth/signup", json=SIGNUP)
    assert resp.status_code == 201
    return client


# --- price <-> plan mapping (pure unit test) ---------------------------------


@dataclass
class _FakeSettings:
    stripe_price_premium: str = "sp_premium"
    stripe_price_family: str = "sp_family"


def test_price_for_plan_and_plan_for_price_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.billing as billing_service

    monkeypatch.setattr(billing_service, "get_settings", lambda: _FakeSettings())

    assert billing_service.price_for_plan(VaultPlan.family) == "sp_family"
    assert billing_service.price_for_plan(VaultPlan.premium) == "sp_premium"
    assert billing_service.plan_for_price("sp_family") == VaultPlan.family
    assert billing_service.plan_for_price("sp_premium") == VaultPlan.premium
    assert billing_service.plan_for_price("unknown-price") is None
    assert billing_service.plan_for_price("") is None
    with pytest.raises(ValueError):
        billing_service.price_for_plan(VaultPlan.free)


# --- checkout / portal gating -------------------------------------------------


async def test_checkout_owner_returns_url_and_audits(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    fake = FakeBilling()
    _override_billing(app, fake)

    resp = await authed.post("/api/v1/billing/checkout", json={"plan": "family"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["url"] == fake.checkout_url
    assert fake.checkout_calls[0]["price_id"] == FAKE_FAMILY_PRICE
    assert fake.checkout_calls[0]["customer_id"] is None  # no BillingCustomer yet

    db = await _session(app)
    row = await db.scalar(select(AuditLog).where(AuditLog.action == "billing.checkout_started"))
    assert row is not None
    assert row.context["plan"] == "family"


async def test_checkout_non_owner_member_forbidden(
    app: FastAPI, authed: AsyncClient, billing_configured: None, emails: CapturingEmail
) -> None:
    await _invite_and_join(app, authed, emails)  # authed is now the spouse (member)
    fake = FakeBilling()
    _override_billing(app, fake)

    resp = await authed.post("/api/v1/billing/checkout", json={"plan": "family"})
    assert resp.status_code == 403


async def test_checkout_unconfigured_returns_503(app: FastAPI, authed: AsyncClient) -> None:
    fake = FakeBilling()
    _override_billing(app, fake)  # billing_configured fixture deliberately not used

    resp = await authed.post("/api/v1/billing/checkout", json={"plan": "premium"})
    assert resp.status_code == 503


async def test_portal_without_billing_customer_is_not_found(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    fake = FakeBilling()
    _override_billing(app, fake)

    resp = await authed.post("/api/v1/billing/portal")
    assert resp.status_code == 404


async def test_portal_returns_url_once_billed(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    vault_id = (await authed.get("/api/v1/vault/usage")).json()["vault_id"]
    fake = FakeBilling()
    fake.event = _event(
        "evt_portal_setup",
        "checkout.session.completed",
        {
            "client_reference_id": vault_id,
            "customer": "cus_portal",
            "subscription": "sub_portal",
            "metadata": {"price_id": FAKE_PREMIUM_PRICE},
        },
    )
    _override_billing(app, fake)
    assert (await _post_webhook(authed)).status_code == 200

    resp = await authed.post("/api/v1/billing/portal")
    assert resp.status_code == 200, resp.text
    assert resp.json()["url"] == fake.portal_url
    assert fake.portal_calls[0]["customer_id"] == "cus_portal"


async def test_summary_reports_plan_and_usage(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    resp = await authed.get("/api/v1/billing/summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plan"] == "free"
    assert body["status"] is None
    assert body["member_count"] == 1


# --- webhook: idempotency, signature, event handling -------------------------


async def test_webhook_checkout_completed_flips_plan_to_family(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    vault_id = (await authed.get("/api/v1/vault/usage")).json()["vault_id"]
    fake = FakeBilling()
    fake.event = _event(
        "evt_checkout_1",
        "checkout.session.completed",
        {
            "client_reference_id": vault_id,
            "customer": "cus_test123",
            "subscription": "sub_test123",
            "metadata": {"price_id": FAKE_FAMILY_PRICE},
        },
    )
    _override_billing(app, fake)

    resp = await _post_webhook(authed)
    assert resp.status_code == 200, resp.text

    db = await _session(app)
    vault = await db.get(Vault, UUID(vault_id))
    assert vault is not None
    assert vault.plan == VaultPlan.family

    customer = await db.scalar(
        select(BillingCustomer).where(BillingCustomer.vault_id == UUID(vault_id))
    )
    assert customer is not None
    assert customer.stripe_customer_id == "cus_test123"
    assert customer.stripe_subscription_id == "sub_test123"
    assert customer.status == "active"

    audit_row = await db.scalar(select(AuditLog).where(AuditLog.action == "billing.plan_changed"))
    assert audit_row is not None
    assert audit_row.context["plan"] == "family"


async def test_webhook_idempotent_replay_processes_once(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    vault_id = (await authed.get("/api/v1/vault/usage")).json()["vault_id"]
    fake = FakeBilling()
    fake.event = _event(
        "evt_replay",
        "checkout.session.completed",
        {
            "client_reference_id": vault_id,
            "customer": "cus_replay",
            "subscription": "sub_replay",
            "metadata": {"price_id": FAKE_PREMIUM_PRICE},
        },
    )
    _override_billing(app, fake)

    first = await _post_webhook(authed)
    second = await _post_webhook(authed)
    assert first.status_code == 200
    assert second.status_code == 200

    db = await _session(app)
    rows = (
        await db.scalars(select(AuditLog).where(AuditLog.action == "billing.plan_changed"))
    ).all()
    assert len(rows) == 1


async def test_webhook_handler_failure_returns_503_and_is_replayable(
    app: FastAPI,
    authed: AsyncClient,
    billing_configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient handler crash must answer non-2xx (so Stripe redelivers) and
    release the event id from the idempotency ledger, so the retry processes."""
    import app.api.v1.endpoints.billing as billing_endpoint

    vault_id = (await authed.get("/api/v1/vault/usage")).json()["vault_id"]
    fake = FakeBilling()
    fake.event = _event(
        "evt_transient",
        "checkout.session.completed",
        {
            "client_reference_id": vault_id,
            "customer": "cus_transient",
            "subscription": "sub_transient",
            "metadata": {"price_id": FAKE_FAMILY_PRICE},
        },
    )
    _override_billing(app, fake)

    async def _boom(db: Any, obj: dict[str, Any]) -> None:
        raise RuntimeError("transient db blip")

    with monkeypatch.context() as m:
        m.setitem(billing_endpoint._HANDLERS, "checkout.session.completed", _boom)
        failed = await _post_webhook(authed)
    assert failed.status_code == 503

    # Stripe redelivers the same event id; with the handler healthy it processes.
    retry = await _post_webhook(authed)
    assert retry.status_code == 200

    db = await _session(app)
    vault = await db.get(Vault, UUID(vault_id))
    assert vault is not None
    assert vault.plan == VaultPlan.family


async def test_webhook_invalid_signature_returns_400(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    fake = FakeBilling()
    fake.raise_on_verify = True
    _override_billing(app, fake)

    resp = await _post_webhook(authed)
    assert resp.status_code == 400


async def test_webhook_subscription_deleted_downgrades_to_free(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    vault_id = (await authed.get("/api/v1/vault/usage")).json()["vault_id"]
    fake = FakeBilling()
    fake.event = _event(
        "evt_del_setup",
        "checkout.session.completed",
        {
            "client_reference_id": vault_id,
            "customer": "cus_del",
            "subscription": "sub_del",
            "metadata": {"price_id": FAKE_FAMILY_PRICE},
        },
    )
    _override_billing(app, fake)
    assert (await _post_webhook(authed)).status_code == 200

    fake.event = _event("evt_del", "customer.subscription.deleted", {"customer": "cus_del"})
    resp = await _post_webhook(authed)
    assert resp.status_code == 200, resp.text

    db = await _session(app)
    vault = await db.get(Vault, UUID(vault_id))
    assert vault is not None
    assert vault.plan == VaultPlan.free
    customer = await db.scalar(
        select(BillingCustomer).where(BillingCustomer.vault_id == UUID(vault_id))
    )
    assert customer is not None
    assert customer.status == "canceled"


async def test_webhook_past_due_keeps_plan_and_audits_payment_failed(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    vault_id = (await authed.get("/api/v1/vault/usage")).json()["vault_id"]
    fake = FakeBilling()
    fake.event = _event(
        "evt_dun_setup",
        "checkout.session.completed",
        {
            "client_reference_id": vault_id,
            "customer": "cus_dun",
            "subscription": "sub_dun",
            "metadata": {"price_id": FAKE_PREMIUM_PRICE},
        },
    )
    _override_billing(app, fake)
    assert (await _post_webhook(authed)).status_code == 200

    fake.event = _event(
        "evt_dun",
        "customer.subscription.updated",
        {
            "customer": "cus_dun",
            "status": "past_due",
            "items": {"data": [{"price": {"id": FAKE_PREMIUM_PRICE}}]},
        },
    )
    resp = await _post_webhook(authed)
    assert resp.status_code == 200, resp.text

    db = await _session(app)
    vault = await db.get(Vault, UUID(vault_id))
    assert vault is not None
    assert vault.plan == VaultPlan.premium  # dunning window: plan retained

    customer = await db.scalar(
        select(BillingCustomer).where(BillingCustomer.vault_id == UUID(vault_id))
    )
    assert customer is not None
    assert customer.status == "past_due"

    audit_row = await db.scalar(select(AuditLog).where(AuditLog.action == "billing.payment_failed"))
    assert audit_row is not None


async def test_webhook_unknown_event_type_ignored(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    fake = FakeBilling()
    fake.event = _event("evt_unknown", "customer.updated", {"customer": "cus_x"})
    _override_billing(app, fake)

    resp = await _post_webhook(authed)
    assert resp.status_code == 200


async def test_webhook_tolerates_missing_linkage(
    app: FastAPI, authed: AsyncClient, billing_configured: None
) -> None:
    """A subscription event for a customer id we've never seen must never 500."""
    fake = FakeBilling()
    fake.event = _event(
        "evt_orphan",
        "customer.subscription.updated",
        {"customer": "cus_never_seen", "status": "active", "items": {"data": []}},
    )
    _override_billing(app, fake)

    resp = await _post_webhook(authed)
    assert resp.status_code == 200


# --- exit criterion: family plan -> pay -> add 6 members ---------------------


async def test_exit_criterion_family_plan_allows_six_members(
    app: FastAPI, authed: AsyncClient, billing_configured: None, emails: CapturingEmail
) -> None:
    """docs/ROADMAP.md M9 exit: "a family can pay $14.99/mo and add 6 members."
    Starts from a free vault, flips it to family via a signed-webhook
    simulation (fake provider, real handler code), then drives the REAL M7
    invite/accept flow (tests/test_family.py) to fill all 6 member seats."""
    vault_id = (await authed.get("/api/v1/vault/usage")).json()["vault_id"]
    fake = FakeBilling()
    fake.event = _event(
        "evt_exit",
        "checkout.session.completed",
        {
            "client_reference_id": vault_id,
            "customer": "cus_exit",
            "subscription": "sub_exit",
            "metadata": {"price_id": FAKE_FAMILY_PRICE},
        },
    )
    _override_billing(app, fake)
    assert (await _post_webhook(authed)).status_code == 200

    db = await _session(app)
    vault = await db.get(Vault, UUID(vault_id))
    assert vault is not None
    assert vault.plan == VaultPlan.family

    # Owner is member #1; invite 5 more through the real invite/accept flow.
    for i in range(5):
        email = f"member{i}@example.com"
        resp = await authed.post("/api/v1/family/invites", json={"email": email, "role": "member"})
        assert resp.status_code == 201, resp.text
        token = _invite_token(emails)

        member_client = await _new_client(app)
        try:
            signup = await member_client.post(
                "/api/v1/auth/signup",
                json={"name": f"Member {i}", "email": email, "password": f"member-pass-{i}"},
            )
            assert signup.status_code == 201, signup.text
            accept = await member_client.post(f"/api/v1/family/invites/{token}/accept")
            assert accept.status_code == 204, accept.text
        finally:
            await member_client.aclose()

    usage = (await authed.get("/api/v1/vault/usage")).json()
    assert usage["member_count"] == 6

    seventh = await authed.post(
        "/api/v1/family/invites", json={"email": "seventh@example.com", "role": "member"}
    )
    assert seventh.status_code == 400
    assert "6 members" in seventh.json()["detail"]
