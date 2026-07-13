import pytest
from httpx import AsyncClient

import app.health as health


async def test_healthz(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def _up() -> bool:
    return True


async def _down() -> bool:
    return False


async def test_readyz_degraded_when_dependency_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health, "_check_database", _up)
    monkeypatch.setattr(health, "_check_redis", _down)
    resp = await client.get("/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"] == {"database": True, "redis": False}


async def test_readyz_ready_when_dependencies_up(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health, "_check_database", _up)
    monkeypatch.setattr(health, "_check_redis", _up)
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


async def test_request_id_header_present(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.headers.get("X-Request-ID")


async def test_request_id_is_propagated(client: AsyncClient) -> None:
    resp = await client.get("/healthz", headers={"X-Request-ID": "test-id-123"})
    assert resp.headers["X-Request-ID"] == "test-id-123"
