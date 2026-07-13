from datetime import date
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.v1.endpoints.documents as documents_endpoint
from app.services.extraction import DocumentExtraction, ExtractedField
from app.services.processing import process_document
from tests.test_documents import PDF_UPLOAD, SIGNUP, FakeStorage  # reuse fixtures' helpers

WASHER_EXTRACTION = DocumentExtraction(
    category="warranties",
    title="Samsung WF45 washer warranty",
    vendor="Samsung",
    document_date=date(2026, 7, 1),
    expiry_date=date(2027, 7, 1),
    amount=899.99,
    currency="USD",
    fields=[
        ExtractedField(label="Model", value="WF45"),
        ExtractedField(label="Term", value="1 year"),
    ],
)


class FakeExtractor:
    def __init__(self, result: DocumentExtraction | None = None) -> None:
        self.result = result or WASHER_EXTRACTION
        self.calls: list[str] = []

    def extract(self, file_bytes: bytes, content_type: str, file_name: str) -> DocumentExtraction:
        self.calls.append(file_name)
        if self.result is None:
            raise RuntimeError("boom")
        return self.result


class FailingExtractor:
    def extract(self, file_bytes: bytes, content_type: str, file_name: str) -> DocumentExtraction:
        raise RuntimeError("model exploded")


@pytest.fixture
def storage(app: FastAPI) -> FakeStorage:
    from app.core.storage import get_storage

    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


@pytest.fixture
def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[UUID]:
    """Pretend extraction is enabled and capture enqueued document ids."""
    calls: list[UUID] = []
    monkeypatch.setattr(documents_endpoint, "extraction_enabled", lambda: True)
    monkeypatch.setattr(documents_endpoint, "_enqueue_extraction", calls.append)
    return calls


@pytest.fixture
async def authed(client: AsyncClient, storage: FakeStorage) -> AsyncClient:
    resp = await client.post("/api/v1/auth/signup", json=SIGNUP)
    assert resp.status_code == 201
    return client


async def _upload(client: AsyncClient, storage: FakeStorage) -> dict[str, Any]:
    resp = await client.post("/api/v1/documents/uploads", json=PDF_UPLOAD)
    ticket = resp.json()
    key = ticket["upload_url"].split("/upload/")[1]
    storage.objects[key] = PDF_UPLOAD["size_bytes"]
    storage.contents = getattr(storage, "contents", {})
    done = await client.post(f"/api/v1/documents/{ticket['document_id']}/complete")
    assert done.status_code == 200, done.text
    return dict(done.json())


async def test_complete_queues_extraction(
    authed: AsyncClient, storage: FakeStorage, enqueued: list[UUID]
) -> None:
    doc = await _upload(authed, storage)
    assert doc["status"] == "queued"
    assert [str(e) for e in enqueued] == [doc["id"]]


async def test_no_extraction_without_api_key(authed: AsyncClient, storage: FakeStorage) -> None:
    doc = await _upload(authed, storage)  # extraction_enabled() is False in tests
    assert doc["status"] == "uploaded"


async def test_ocr_quota_gates_extraction(
    authed: AsyncClient,
    storage: FakeStorage,
    enqueued: list[UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.core.quotas as quotas
    from app.core.quotas import PlanLimits
    from app.models.vault import VaultPlan

    monkeypatch.setitem(
        quotas.PLAN_LIMITS,
        VaultPlan.free,
        PlanLimits(max_documents=25, max_storage_bytes=100 * 1024 * 1024, ocr_per_month=1),
    )
    first = await _upload(authed, storage)
    second = await _upload(authed, storage)
    assert first["status"] == "queued"
    assert second["status"] == "uploaded"  # over quota → stored without AI
    assert len(enqueued) == 1


class BytesStorage(FakeStorage):
    async def get_object(self, key: str) -> bytes:
        return b"%PDF-1.4 fake receipt bytes"


async def _queued_document_id(client: AsyncClient, storage: FakeStorage) -> UUID:
    doc = await _upload(client, storage)
    return UUID(doc["id"])


@pytest.fixture
def bytes_storage(app: FastAPI) -> BytesStorage:
    from app.core.storage import get_storage

    fake = BytesStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


async def _session(app: FastAPI) -> AsyncSession:
    from app.db.session import get_db_session

    factory = app.dependency_overrides[get_db_session]
    return await factory().__anext__()  # type: ignore[no-any-return]


async def test_process_document_extracts(
    app: FastAPI, authed: AsyncClient, bytes_storage: BytesStorage, enqueued: list[UUID]
) -> None:
    doc_id = await _queued_document_id(authed, bytes_storage)
    extractor = FakeExtractor()

    db = await _session(app)
    ok = await process_document(db, bytes_storage, extractor, doc_id)
    assert ok is True

    listed = (await authed.get("/api/v1/documents")).json()[0]
    assert listed["status"] == "extracted"
    assert listed["category"] == "warranties"
    assert listed["title"] == "Samsung WF45 washer warranty"
    assert listed["expiry_date"] == "2027-07-01"
    assert listed["extracted"]["vendor"] == "Samsung"
    assert listed["extracted"]["fields"][0] == {"label": "Model", "value": "WF45"}


async def test_process_document_failure_marks_failed(
    app: FastAPI, authed: AsyncClient, bytes_storage: BytesStorage, enqueued: list[UUID]
) -> None:
    doc_id = await _queued_document_id(authed, bytes_storage)

    db = await _session(app)
    ok = await process_document(db, bytes_storage, FailingExtractor(), doc_id)
    assert ok is False

    listed = (await authed.get("/api/v1/documents")).json()[0]
    assert listed["status"] == "failed"


async def test_process_document_skips_non_queued(
    app: FastAPI, authed: AsyncClient, storage: FakeStorage
) -> None:
    doc = await _upload(authed, storage)  # stays "uploaded" (no key in tests)
    db = await _session(app)
    ok = await process_document(db, storage, FakeExtractor(), UUID(doc["id"]))
    assert ok is False
