from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

import app.api.v1.endpoints.documents as documents_endpoint
from app.services.processing import process_document
from app.services.search import build_search_text, make_snippet
from tests.test_documents import SIGNUP, FakeStorage
from tests.test_extraction import BytesStorage, FakeExtractor


@pytest.fixture
def storage(app: FastAPI) -> BytesStorage:
    from app.core.storage import get_storage

    fake = BytesStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


@pytest.fixture
def extraction_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(documents_endpoint, "extraction_enabled", lambda: True)
    monkeypatch.setattr(documents_endpoint, "_enqueue_extraction", lambda _id: None)


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


async def _extract(app: FastAPI, storage: Any, doc_id: str) -> None:
    from app.db.session import get_db_session

    factory = app.dependency_overrides[get_db_session]
    db = await factory().__anext__()
    assert await process_document(db, storage, FakeExtractor(), UUID(doc_id))


async def test_search_finds_by_title(authed: AsyncClient, storage: BytesStorage) -> None:
    await _upload(authed, storage, "passport-scan.pdf")
    resp = await authed.get("/api/v1/search", params={"q": "passport"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["title"] == "passport-scan"
    assert "passport" in body["results"][0]["snippet"].lower()
    assert body["latency_ms"] >= 0


async def test_search_finds_extracted_content(
    app: FastAPI, authed: AsyncClient, storage: BytesStorage, extraction_on: None
) -> None:
    doc_id = await _upload(authed, storage, "receipt-scan-001.pdf")
    await _extract(app, storage, doc_id)

    # "Samsung Washer" appears only in extracted fields, not the filename
    resp = await authed.get("/api/v1/search", params={"q": "Samsung washer"})
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["title"] == "Samsung WF45 washer warranty"
    assert body["results"][0]["category"] == "warranties"
    assert body["results"][0]["score"] > 0


async def test_search_category_filter_and_counts(
    app: FastAPI, authed: AsyncClient, storage: BytesStorage, extraction_on: None
) -> None:
    extracted_id = await _upload(authed, storage, "samsung-receipt.pdf")
    await _extract(app, storage, extracted_id)
    await _upload(authed, storage, "samsung-tv-manual.pdf")  # stays "other"

    unfiltered = (await authed.get("/api/v1/search", params={"q": "samsung"})).json()
    assert unfiltered["total"] == 2
    assert unfiltered["counts"] == {"warranties": 1, "other": 1}

    filtered = (
        await authed.get("/api/v1/search", params={"q": "samsung", "category": "warranties"})
    ).json()
    assert len(filtered["results"]) == 1
    assert filtered["counts"] == {"warranties": 1, "other": 1}  # chips keep full counts


async def test_search_no_results(authed: AsyncClient, storage: BytesStorage) -> None:
    await _upload(authed, storage, "receipt.pdf")
    body = (await authed.get("/api/v1/search", params={"q": "zeppelin"})).json()
    assert body["total"] == 0
    assert body["results"] == []


async def test_search_is_vault_scoped(authed: AsyncClient, storage: BytesStorage) -> None:
    await _upload(authed, storage, "secret-passport.pdf")
    authed.cookies.clear()
    await authed.post(
        "/api/v1/auth/signup",
        json={"name": "Other", "email": "other@example.com", "password": "other-pass-1"},
    )
    body = (await authed.get("/api/v1/search", params={"q": "passport"})).json()
    assert body["total"] == 0


async def test_search_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/search", params={"q": "x"})).status_code == 401


def test_build_search_text_flattens_extraction() -> None:
    text = build_search_text(
        "Samsung WF45 washer warranty",
        "receipt.pdf",
        {
            "vendor": "Samsung",
            "amount": 899.99,
            "expiry_date": "2027-07-01",
            "fields": [{"label": "Model", "value": "WF45"}],
        },
        "warranties",
    )
    for token in ("Samsung", "899.99", "2027-07-01", "Model WF45", "warranties"):
        assert token in text


def test_make_snippet_windows_around_hit() -> None:
    text = "x" * 200 + " Samsung WF45 washer " + "y" * 200
    snippet = make_snippet(text, "washer")
    assert "washer" in snippet
    assert snippet.startswith("…") and snippet.endswith("…")
    assert len(snippet) < 200
