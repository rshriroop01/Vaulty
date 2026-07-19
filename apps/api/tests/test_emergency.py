import pytest
from fastapi import FastAPI
from httpx import AsyncClient

import app.api.v1.endpoints.emergency as emergency_endpoint
from tests.test_documents import SIGNUP, FakeStorage

BINDER = {
    "contacts": [{"name": "Priya Roy", "phone": "+1 555 0100", "relation": "Spouse"}],
    "medical": {
        "blood_group": "B+",
        "allergies": "penicillin",
        "medications": "metformin 500mg",
        "hospital": "City General",
    },
    "delegates": [{"name": "Priya Roy", "relation": "Spouse"}],
}


class CapturingEmail:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


@pytest.fixture
def emails(monkeypatch: pytest.MonkeyPatch) -> CapturingEmail:
    capture = CapturingEmail()
    monkeypatch.setattr(emergency_endpoint, "get_email_provider", lambda: capture)
    return capture


@pytest.fixture
def storage(app: FastAPI) -> FakeStorage:
    from app.core.storage import get_storage

    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


@pytest.fixture
async def owner(client: AsyncClient, storage: FakeStorage) -> AsyncClient:
    resp = await client.post("/api/v1/auth/signup", json=SIGNUP)
    assert resp.status_code == 201
    return client


async def test_binder_update_and_checklist(owner: AsyncClient) -> None:
    empty = (await owner.get("/api/v1/emergency")).json()
    assert all(item["done"] is False for item in empty["checklist"])
    assert empty["qr_active"] is False

    updated = (await owner.put("/api/v1/emergency", json=BINDER)).json()
    done = {item["key"]: item["done"] for item in updated["checklist"]}
    assert done["contacts"] and done["medical"] and done["medications"]
    assert not done["insurance"] and not done["ids"]  # no docs uploaded


async def test_qr_issue_and_public_access(owner: AsyncClient, emails: CapturingEmail) -> None:
    await owner.put("/api/v1/emergency", json=BINDER)
    issued = await owner.post("/api/v1/emergency/qr", json={"pin": "4321"})
    assert issued.status_code == 200
    token = issued.json()["token"]

    # The PRD journey: no credentials — clear the session entirely
    owner.cookies.clear()
    granted = await owner.post(f"/api/v1/emergency/access/{token}", json={"pin": "4321"})
    assert granted.status_code == 200
    body = granted.json()
    assert body["medical"]["blood_group"] == "B+"
    assert body["contacts"][0]["name"] == "Priya Roy"

    # Owner was notified of the scan
    assert any("accessed" in subject for _, subject, _ in emails.sent)


async def test_public_access_wrong_pin(owner: AsyncClient, emails: CapturingEmail) -> None:
    await owner.put("/api/v1/emergency", json=BINDER)
    token = (await owner.post("/api/v1/emergency/qr", json={"pin": "4321"})).json()["token"]

    owner.cookies.clear()
    denied = await owner.post(f"/api/v1/emergency/access/{token}", json={"pin": "9999"})
    assert denied.status_code == 401
    assert any("failed" in subject for _, subject, _ in emails.sent)


async def test_revoked_token_is_dead(owner: AsyncClient, emails: CapturingEmail) -> None:
    token = (await owner.post("/api/v1/emergency/qr", json={"pin": "4321"})).json()["token"]
    assert (await owner.post("/api/v1/emergency/qr/revoke")).status_code == 204

    owner.cookies.clear()
    resp = await owner.post(f"/api/v1/emergency/access/{token}", json={"pin": "4321"})
    assert resp.status_code == 404


async def test_reissue_revokes_previous(owner: AsyncClient, emails: CapturingEmail) -> None:
    first = (await owner.post("/api/v1/emergency/qr", json={"pin": "1111"})).json()["token"]
    second = (await owner.post("/api/v1/emergency/qr", json={"pin": "2222"})).json()["token"]

    owner.cookies.clear()
    assert (
        await owner.post(f"/api/v1/emergency/access/{first}", json={"pin": "1111"})
    ).status_code == 404
    assert (
        await owner.post(f"/api/v1/emergency/access/{second}", json={"pin": "2222"})
    ).status_code == 200


async def test_scan_appears_in_access_log(owner: AsyncClient, emails: CapturingEmail) -> None:
    token = (await owner.post("/api/v1/emergency/qr", json={"pin": "4321"})).json()["token"]
    cookies = dict(owner.cookies)
    owner.cookies.clear()
    await owner.post(f"/api/v1/emergency/access/{token}", json={"pin": "4321"})

    for name, value in cookies.items():
        owner.cookies.set(name, value)
    binder = (await owner.get("/api/v1/emergency")).json()
    assert binder["qr_active"] is True
    assert any(entry["action"] == "emergency.scan" for entry in binder["access_log"])
