import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from tests.test_documents import SIGNUP, FakeStorage, _upload


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


async def test_patch_category_and_title(authed: AsyncClient, storage: FakeStorage) -> None:
    doc = await _upload(authed, storage)
    resp = await authed.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"category": "medical", "title": "City Hospital ER visit"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "medical"
    assert body["title"] == "City Hospital ER visit"

    # Recategorized doc is findable under the new title (search_text rebuilt)
    found = (await authed.get("/api/v1/search", params={"q": "hospital"})).json()
    assert found["total"] == 1


async def test_patch_bill_status(authed: AsyncClient, storage: FakeStorage) -> None:
    doc = await _upload(authed, storage)
    for status in ("pending", "paid", "outstanding"):
        resp = await authed.patch(f"/api/v1/documents/{doc['id']}", json={"bill_status": status})
        assert resp.status_code == 200
        assert resp.json()["bill_status"] == status


async def test_patch_rejects_bad_bill_status(authed: AsyncClient, storage: FakeStorage) -> None:
    doc = await _upload(authed, storage)
    resp = await authed.patch(f"/api/v1/documents/{doc['id']}", json={"bill_status": "maybe"})
    assert resp.status_code == 400


async def test_patch_is_vault_scoped(authed: AsyncClient, storage: FakeStorage) -> None:
    doc = await _upload(authed, storage)
    authed.cookies.clear()
    await authed.post(
        "/api/v1/auth/signup",
        json={"name": "Other", "email": "other@example.com", "password": "other-pass-1"},
    )
    resp = await authed.patch(f"/api/v1/documents/{doc['id']}", json={"title": "hijack"})
    assert resp.status_code == 404


async def test_list_filters_by_category(authed: AsyncClient, storage: FakeStorage) -> None:
    a = await _upload(authed, storage)
    await _upload(authed, storage, file_name="second receipt.pdf")
    await authed.patch(f"/api/v1/documents/{a['id']}", json={"category": "insurance"})

    insurance = (await authed.get("/api/v1/documents", params={"category": "insurance"})).json()
    assert [d["id"] for d in insurance] == [a["id"]]
    everything = (await authed.get("/api/v1/documents")).json()
    assert len(everything) == 2
