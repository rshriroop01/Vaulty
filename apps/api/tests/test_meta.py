from httpx import AsyncClient


async def test_version_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/meta/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "vaultly-api"
    assert body["api_version"] == "v1"


async def test_openapi_served_under_version_prefix(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Vaultly API"
