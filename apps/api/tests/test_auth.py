from httpx import AsyncClient

SIGNUP = {"name": "Shriroop Roy", "email": "shriroop@example.com", "password": "correct-horse-1"}


async def _signup(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/signup", json=SIGNUP)
    assert resp.status_code == 201, resp.text


async def test_signup_creates_user_and_personal_vault(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/signup", json=SIGNUP)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "shriroop@example.com"
    assert len(body["vaults"]) == 1
    assert body["vaults"][0]["name"] == "Shriroop's Vault"
    assert body["vaults"][0]["role"] == "owner"
    assert body["vaults"][0]["plan"] == "free"
    # Auth cookies set
    assert "vaultly_access" in resp.cookies
    assert "vaultly_refresh" in resp.cookies


async def test_signup_duplicate_email_conflicts(client: AsyncClient) -> None:
    await _signup(client)
    resp = await client.post("/api/v1/auth/signup", json=SIGNUP)
    assert resp.status_code == 409


async def test_signup_weak_password_rejected(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/signup", json={**SIGNUP, "password": "onlyletters"})
    assert resp.status_code == 422


async def test_login_and_me(client: AsyncClient) -> None:
    await _signup(client)
    client.cookies.clear()

    resp = await client.post(
        "/api/v1/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}
    )
    assert resp.status_code == 200

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["name"] == "Shriroop Roy"


async def test_login_wrong_password(client: AsyncClient) -> None:
    await _signup(client)
    client.cookies.clear()
    resp = await client.post(
        "/api/v1/auth/login", json={"email": SIGNUP["email"], "password": "wrong-password-1"}
    )
    assert resp.status_code == 401


async def test_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_refresh_rotates_token(client: AsyncClient) -> None:
    await _signup(client)
    old_refresh = client.cookies["vaultly_refresh"]

    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert client.cookies["vaultly_refresh"] != old_refresh

    # The old (rotated-out) token must be dead
    client.cookies.set("vaultly_refresh", old_refresh, path="/api/v1/auth")
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_logout_revokes_session(client: AsyncClient) -> None:
    await _signup(client)
    refresh = client.cookies["vaultly_refresh"]

    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 204

    client.cookies.set("vaultly_refresh", refresh, path="/api/v1/auth")
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_garbage_access_token_rejected(client: AsyncClient) -> None:
    client.cookies.set("vaultly_access", "not-a-jwt")
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
