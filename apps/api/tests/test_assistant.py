from datetime import date

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.v1.endpoints.assistant as assistant_endpoint
from app.models import AuditLog, FeatureFlag, User, Vault, VaultMembership, VaultPlan
from app.services.assistant import (
    AssistantAnswer,
    SuggestedAction,
    apply_guardrails,
    get_assistant,
)
from tests.test_documents import SIGNUP, FakeStorage

FLAG_KEY = "assistant"


async def _session(app: FastAPI) -> AsyncSession:
    from app.db.session import get_db_session

    factory = app.dependency_overrides[get_db_session]
    return await factory().__anext__()  # type: ignore[no-any-return]


async def _set_flag(app: FastAPI, enabled: bool) -> None:
    db = await _session(app)
    flag = await db.get(FeatureFlag, FLAG_KEY)
    if flag is None:
        db.add(FeatureFlag(key=FLAG_KEY, enabled=enabled))
    else:
        flag.enabled = enabled
    await db.commit()


async def _set_plan(app: FastAPI, email: str, plan: VaultPlan) -> None:
    db = await _session(app)
    user = await db.scalar(select(User).where(User.email == email))
    assert user is not None
    membership = await db.scalar(select(VaultMembership).where(VaultMembership.user_id == user.id))
    assert membership is not None
    vault = await db.get(Vault, membership.vault_id)
    assert vault is not None
    vault.plan = plan
    await db.commit()


class FakeAssistant:
    def __init__(self, answer: AssistantAnswer) -> None:
        self.answer = answer
        self.calls: list[str] = []

    def ask(self, question: str, documents: list) -> AssistantAnswer:  # type: ignore[type-arg]
        self.calls.append(question)
        return self.answer


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


async def _upload(client: AsyncClient, storage: FakeStorage, file_name: str) -> str:
    resp = await client.post(
        "/api/v1/documents/uploads",
        json={"file_name": file_name, "content_type": "application/pdf", "size_bytes": 1000},
    )
    ticket = resp.json()
    key = ticket["upload_url"].split("/upload/")[1]
    storage.objects[key] = 1000
    done = await client.post(f"/api/v1/documents/{ticket['document_id']}/complete")
    assert done.status_code == 200, done.text
    return str(ticket["document_id"])


def _override_assistant(app: FastAPI, fake: FakeAssistant) -> None:
    app.dependency_overrides[get_assistant] = lambda: fake


@pytest.fixture
def api_key_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real gate checks ANTHROPIC_API_KEY (empty in test env, like extraction);
    tests that need to reach the fake Claude call flip it on, mirroring how
    test_extraction.py monkeypatches extraction_enabled."""
    monkeypatch.setattr(assistant_endpoint, "assistant_enabled", lambda: True)


# --- happy path -------------------------------------------------------------


async def test_ask_happy_path_returns_answer_with_citations(
    app: FastAPI, authed: AsyncClient, storage: FakeStorage, api_key_configured: None
) -> None:
    doc_id = await _upload(authed, storage, "washer-warranty.pdf")
    await _set_flag(app, True)
    await _set_plan(app, SIGNUP["email"], VaultPlan.premium)
    fake = FakeAssistant(
        AssistantAnswer(
            answer="Your washer warranty expires 2027-07-01.",
            citations=[doc_id],
            suggested_actions=[
                SuggestedAction(
                    type="create_reminder",
                    document_id=doc_id,
                    label="Remind me before it expires",
                    date=date(2027, 7, 1),
                )
            ],
        )
    )
    _override_assistant(app, fake)

    question = "when does my washer warranty expire?"
    resp = await authed.post("/api/v1/assistant/ask", json={"question": question})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"] == "Your washer warranty expires 2027-07-01."
    assert body["citations"] == [
        {"document_id": doc_id, "title": "washer-warranty", "category": "other"}
    ]
    assert body["suggested_actions"][0]["document_id"] == doc_id
    assert body["retrieved_count"] >= 1
    assert body["latency_ms"] >= 0
    assert fake.calls == [question]

    db = await _session(app)
    row = await db.scalar(select(AuditLog).where(AuditLog.action == "assistant.ask"))
    assert row is not None
    assert row.context["retrieved_count"] >= 1
    assert row.context["question_length"] == len(question)


# --- gates -------------------------------------------------------------------


async def test_free_vault_gets_plan_upgrade_error(
    app: FastAPI, authed: AsyncClient, storage: FakeStorage
) -> None:
    await _upload(authed, storage, "receipt.pdf")
    await _set_flag(app, True)
    # vault stays on the default free plan
    _override_assistant(app, FakeAssistant(AssistantAnswer(answer="n/a")))

    resp = await authed.post("/api/v1/assistant/ask", json={"question": "anything?"})
    assert resp.status_code == 403
    body = resp.json()
    assert body["type"].endswith("/plan-upgrade-required")
    assert "premium" in body["detail"].lower()


async def test_flag_off_is_gated(app: FastAPI, authed: AsyncClient, storage: FakeStorage) -> None:
    await _upload(authed, storage, "receipt.pdf")
    await _set_plan(app, SIGNUP["email"], VaultPlan.premium)
    await _set_flag(app, False)
    _override_assistant(app, FakeAssistant(AssistantAnswer(answer="n/a")))

    resp = await authed.post("/api/v1/assistant/ask", json={"question": "anything?"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Assistant is not enabled"


async def test_no_api_key_returns_503(
    app: FastAPI, authed: AsyncClient, storage: FakeStorage
) -> None:
    await _upload(authed, storage, "receipt.pdf")
    await _set_flag(app, True)
    await _set_plan(app, SIGNUP["email"], VaultPlan.premium)
    _override_assistant(app, FakeAssistant(AssistantAnswer(answer="n/a")))
    # api_key_configured fixture deliberately not used: ANTHROPIC_API_KEY is empty

    resp = await authed.post("/api/v1/assistant/ask", json={"question": "anything?"})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Assistant unavailable"


async def test_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/assistant/ask", json={"question": "anything?"})
    assert resp.status_code == 401


# --- cross-tenant guardrail ---------------------------------------------------


async def test_cross_tenant_guardrail(
    app: FastAPI, client: AsyncClient, storage: FakeStorage, api_key_configured: None
) -> None:
    # Vault A
    resp = await client.post("/api/v1/auth/signup", json=SIGNUP)
    assert resp.status_code == 201
    doc_a = await _upload(client, storage, "vaultA-secret-policy.pdf")

    # Vault B — different user, different vault
    client.cookies.clear()
    other = {"name": "Other", "email": "other-assistant@example.com", "password": "other-pass-1"}
    resp = await client.post("/api/v1/auth/signup", json=other)
    assert resp.status_code == 201
    doc_b = await _upload(client, storage, "vaultB-secret-policy.pdf")
    client.cookies.clear()

    # Back to vault A
    resp = await client.post(
        "/api/v1/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}
    )
    assert resp.status_code == 200

    await _set_flag(app, True)
    await _set_plan(app, SIGNUP["email"], VaultPlan.premium)

    # A hallucinating/malicious model citing vault B's document id
    fake = FakeAssistant(
        AssistantAnswer(
            answer="Found it.",
            citations=[doc_a, doc_b],
            suggested_actions=[
                SuggestedAction(type="open_document", document_id=doc_b, label="Open it")
            ],
        )
    )
    _override_assistant(app, fake)

    resp = await client.post("/api/v1/assistant/ask", json={"question": "secret policy"})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    cited_ids = {c["document_id"] for c in body["citations"]}
    assert doc_b not in cited_ids
    assert all(a["document_id"] != doc_b for a in body["suggested_actions"])
    # retrieval itself never saw vault B's document
    assert doc_a in cited_ids or body["retrieved_count"] >= 1


# --- pure post-filter unit test ------------------------------------------------


def test_apply_guardrails_drops_hallucinated_ids() -> None:
    answer = AssistantAnswer(
        answer="x",
        citations=["real-id", "hallucinated-id"],
        suggested_actions=[
            SuggestedAction(type="open_document", document_id="real-id", label="Open"),
            SuggestedAction(type="open_document", document_id="hallucinated-id", label="Open"),
        ],
    )
    filtered = apply_guardrails(answer, {"real-id"})
    assert filtered.citations == ["real-id"]
    assert len(filtered.suggested_actions) == 1
    assert filtered.suggested_actions[0].document_id == "real-id"
