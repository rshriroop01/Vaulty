from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.reminders import run_reminder_scan
from tests.test_documents import SIGNUP, FakeStorage

TODAY = date(2026, 7, 14)


class FakeEmail:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        if self.fail:
            raise RuntimeError("smtp down")
        self.sent.append((to, subject))


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


async def _session(app: FastAPI) -> AsyncSession:
    from app.db.session import get_db_session

    factory = app.dependency_overrides[get_db_session]
    return await factory().__anext__()  # type: ignore[no-any-return]


async def _create(
    client: AsyncClient, days_out: int, title: str = "Washer warranty expires"
) -> dict:
    resp = await client.post(
        "/api/v1/reminders",
        json={"title": title, "due_date": (TODAY + timedelta(days=days_out)).isoformat()},
    )
    assert resp.status_code == 201, resp.text
    return dict(resp.json())


async def test_create_and_list(authed: AsyncClient) -> None:
    created = await _create(authed, 20)
    assert created["lead_times"] == [30, 7, 1]
    assert created["completed"] is False

    listed = (await authed.get("/api/v1/reminders")).json()
    assert [r["id"] for r in listed] == [created["id"]]


async def test_complete_hides_from_list(authed: AsyncClient) -> None:
    created = await _create(authed, 20)
    patched = (
        await authed.patch(f"/api/v1/reminders/{created['id']}", json={"completed": True})
    ).json()
    assert patched["completed"] is True
    assert (await authed.get("/api/v1/reminders")).json() == []


async def test_reminder_linked_to_document(authed: AsyncClient, storage: FakeStorage) -> None:
    from tests.test_documents import _upload

    doc = await _upload(authed, storage)
    resp = await authed.post(
        "/api/v1/reminders",
        json={
            "title": f"{doc['title']} expires",
            "due_date": (TODAY + timedelta(days=30)).isoformat(),
            "document_id": doc["id"],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["document_title"] == doc["title"]


async def test_reminder_rejects_foreign_document(authed: AsyncClient, storage: FakeStorage) -> None:
    from tests.test_documents import _upload

    doc = await _upload(authed, storage)
    authed.cookies.clear()
    await authed.post(
        "/api/v1/auth/signup",
        json={"name": "Other", "email": "other@example.com", "password": "other-pass-1"},
    )
    resp = await authed.post(
        "/api/v1/reminders",
        json={"title": "x", "due_date": TODAY.isoformat(), "document_id": doc["id"]},
    )
    assert resp.status_code == 404


async def test_scan_sends_most_imminent_lead_once(app: FastAPI, authed: AsyncClient) -> None:
    await _create(authed, 5)  # within 7d and 30d leads; 7d is most imminent pending
    email = FakeEmail()
    db = await _session(app)

    stats = await run_reminder_scan(db, email, today=TODAY)
    assert stats == {"sent": 1, "failed": 0, "skipped": 1}  # 30d retired, 7d sent
    assert len(email.sent) == 1
    to, subject = email.sent[0]
    assert to == SIGNUP["email"]
    assert "in 5 days" in subject

    # Second scan: idempotent, nothing new
    stats = await run_reminder_scan(db, email, today=TODAY)
    assert stats == {"sent": 0, "failed": 0, "skipped": 0}
    assert len(email.sent) == 1


async def test_scan_fires_again_at_next_lead(app: FastAPI, authed: AsyncClient) -> None:
    await _create(authed, 8)
    email = FakeEmail()
    db = await _session(app)

    assert (await run_reminder_scan(db, email, today=TODAY))["sent"] == 1  # 30d lead
    assert (await run_reminder_scan(db, email, today=TODAY + timedelta(days=7)))["sent"] == 1  # 7d
    assert (await run_reminder_scan(db, email, today=TODAY + timedelta(days=7)))["sent"] == 0


async def test_scan_ignores_completed_and_future(app: FastAPI, authed: AsyncClient) -> None:
    done = await _create(authed, 3)
    await authed.patch(f"/api/v1/reminders/{done['id']}", json={"completed": True})
    await _create(authed, 200)  # no lead time due yet

    email = FakeEmail()
    db = await _session(app)
    assert (await run_reminder_scan(db, email, today=TODAY))["sent"] == 0
    assert email.sent == []


async def test_scan_records_failures(app: FastAPI, authed: AsyncClient) -> None:
    await _create(authed, 5)
    db = await _session(app)
    stats = await run_reminder_scan(db, FakeEmail(fail=True), today=TODAY)
    assert stats["failed"] == 1

    stats_resp = (await authed.get("/api/v1/reminders/stats")).json()
    assert stats_resp["failed_total"] == 1
    assert stats_resp["delivery_rate"] == 0.0


async def test_stats(authed: AsyncClient, app: FastAPI) -> None:
    await _create(authed, 10)
    await _create(authed, 100)
    email = FakeEmail()
    db = await _session(app)
    await run_reminder_scan(db, email, today=TODAY)

    stats = (await authed.get("/api/v1/reminders/stats")).json()
    assert stats["total_active"] == 2
    assert stats["needs_attention"] == 1
    assert stats["sent_total"] == 1
    assert stats["delivery_rate"] == 1.0


async def test_reminders_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/reminders")).status_code == 401
