from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

import app.core.quotas as quotas
from app.core.quotas import PlanLimits
from app.core.storage import get_storage
from app.models.vault import VaultPlan

SIGNUP = {"name": "Doc Tester", "email": "docs@example.com", "password": "docs-pass-1"}
PDF_UPLOAD = {
    "file_name": "receipt 2026.pdf",
    "content_type": "application/pdf",
    "size_bytes": 1000,
}


class FakeStorage:
    """In-memory stand-in for MinIO/S3."""

    def __init__(self) -> None:
        self.objects: dict[str, int] = {}
        self.deleted: list[str] = []

    async def presign_upload(self, key: str, content_type: str) -> str:
        return f"https://storage.test/upload/{key}"

    async def presign_download(self, key: str, file_name: str) -> str:
        return f"https://storage.test/download/{key}"

    async def object_size(self, key: str) -> int | None:
        return self.objects.get(key)

    async def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)
        self.deleted.append(key)


@pytest.fixture
def storage(app: FastAPI) -> FakeStorage:
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


@pytest.fixture
async def authed(client: AsyncClient, storage: FakeStorage) -> AsyncClient:
    resp = await client.post("/api/v1/auth/signup", json=SIGNUP)
    assert resp.status_code == 201
    return client


async def _upload(client: AsyncClient, storage: FakeStorage, **overrides: Any) -> dict[str, Any]:
    """Full happy-path upload: initiate → 'PUT to storage' → complete."""
    resp = await client.post("/api/v1/documents/uploads", json={**PDF_UPLOAD, **overrides})
    assert resp.status_code == 201, resp.text
    ticket = resp.json()
    key = ticket["upload_url"].split("/upload/")[1]
    storage.objects[key] = overrides.get("size_bytes", PDF_UPLOAD["size_bytes"])
    done = await client.post(f"/api/v1/documents/{ticket['document_id']}/complete")
    assert done.status_code == 200, done.text
    return dict(done.json())


async def test_upload_round_trip(authed: AsyncClient, storage: FakeStorage) -> None:
    doc = await _upload(authed, storage)
    assert doc["status"] == "uploaded"
    assert doc["title"] == "receipt 2026"
    assert doc["category"] == "other"

    listed = (await authed.get("/api/v1/documents")).json()
    assert [d["id"] for d in listed] == [doc["id"]]

    dl = await authed.get(f"/api/v1/documents/{doc['id']}/download")
    assert dl.status_code == 200
    assert dl.json()["url"].startswith("https://storage.test/download/")


async def test_complete_is_idempotent(authed: AsyncClient, storage: FakeStorage) -> None:
    doc = await _upload(authed, storage)
    again = await authed.post(f"/api/v1/documents/{doc['id']}/complete")
    assert again.status_code == 200
    assert again.json()["status"] == "uploaded"


async def test_complete_without_object_fails(authed: AsyncClient, storage: FakeStorage) -> None:
    resp = await authed.post("/api/v1/documents/uploads", json=PDF_UPLOAD)
    ticket = resp.json()
    done = await authed.post(f"/api/v1/documents/{ticket['document_id']}/complete")
    assert done.status_code == 400
    # Unconfirmed uploads never appear in the vault
    assert (await authed.get("/api/v1/documents")).json() == []


async def test_delete_removes_object_and_row(authed: AsyncClient, storage: FakeStorage) -> None:
    doc = await _upload(authed, storage)
    resp = await authed.delete(f"/api/v1/documents/{doc['id']}")
    assert resp.status_code == 204
    assert len(storage.deleted) == 1
    assert (await authed.get("/api/v1/documents")).json() == []


async def test_size_and_type_limits(authed: AsyncClient, storage: FakeStorage) -> None:
    too_big = await authed.post(
        "/api/v1/documents/uploads", json={**PDF_UPLOAD, "size_bytes": 26 * 1024 * 1024}
    )
    assert too_big.status_code == 400
    bad_type = await authed.post(
        "/api/v1/documents/uploads", json={**PDF_UPLOAD, "content_type": "application/zip"}
    )
    assert bad_type.status_code == 400


async def test_document_count_quota(
    authed: AsyncClient, storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        quotas.PLAN_LIMITS,
        VaultPlan.free,
        PlanLimits(max_documents=1, max_storage_bytes=100 * 1024 * 1024, ocr_per_month=5),
    )
    await _upload(authed, storage)
    resp = await authed.post("/api/v1/documents/uploads", json=PDF_UPLOAD)
    assert resp.status_code == 402
    assert "free plan" in resp.json()["detail"]


async def test_storage_quota(
    authed: AsyncClient, storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        quotas.PLAN_LIMITS,
        VaultPlan.free,
        PlanLimits(max_documents=25, max_storage_bytes=1500, ocr_per_month=5),
    )
    await _upload(authed, storage)  # 1000 bytes
    resp = await authed.post("/api/v1/documents/uploads", json=PDF_UPLOAD)  # would be 2000
    assert resp.status_code == 402
    assert "storage" in resp.json()["detail"].lower()


async def test_documents_require_auth(client: AsyncClient, storage: FakeStorage) -> None:
    assert (await client.get("/api/v1/documents")).status_code == 401


async def test_cross_vault_isolation(authed: AsyncClient, storage: FakeStorage) -> None:
    doc = await _upload(authed, storage)
    # Second user must not see or reach the first user's document
    authed.cookies.clear()
    await authed.post(
        "/api/v1/auth/signup",
        json={"name": "Other", "email": "other@example.com", "password": "other-pass-1"},
    )
    assert (await authed.get("/api/v1/documents")).json() == []
    assert (await authed.get(f"/api/v1/documents/{doc['id']}/download")).status_code == 404
    assert (await authed.delete(f"/api/v1/documents/{doc['id']}")).status_code == 404


async def test_vault_usage(authed: AsyncClient, storage: FakeStorage) -> None:
    await _upload(authed, storage)
    usage = (await authed.get("/api/v1/vault/usage")).json()
    assert usage["document_count"] == 1
    assert usage["storage_bytes"] == 1000
    assert usage["document_limit"] == 25
    assert usage["member_count"] == 1
    assert usage["categories"]["other"] == 1
    assert usage["categories"]["receipts"] == 0
