from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.errors import PROBLEM_CONTENT_TYPE, NotFoundError
from app.main import create_app


@pytest.fixture
async def erroring_client() -> AsyncIterator[AsyncClient]:
    app = create_app()

    @app.get("/boom-domain")
    async def boom_domain() -> None:
        raise NotFoundError("Document not found")

    @app.get("/boom-unhandled")
    async def boom_unhandled() -> None:
        raise RuntimeError("something broke")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_domain_error_is_problem_json(erroring_client: AsyncClient) -> None:
    resp = await erroring_client.get("/boom-domain")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    body = resp.json()
    assert body["title"] == "Not Found"
    assert body["detail"] == "Document not found"


async def test_unhandled_error_is_sanitized_500(erroring_client: AsyncClient) -> None:
    resp = await erroring_client.get("/boom-unhandled")
    assert resp.status_code == 500
    body = resp.json()
    assert body["title"] == "Internal Server Error"
    assert "something broke" not in body["detail"]  # internals never leak to clients


async def test_unknown_route_is_problem_json(erroring_client: AsyncClient) -> None:
    resp = await erroring_client.get("/nope")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
