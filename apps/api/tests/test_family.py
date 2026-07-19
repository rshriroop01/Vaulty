import pytest
from fastapi import FastAPI
from httpx import AsyncClient

import app.api.v1.endpoints.family as family_endpoint
from tests.test_documents import SIGNUP, FakeStorage, _upload

SPOUSE = {"name": "Priya Roy", "email": "priya@example.com", "password": "spouse-pass-1"}


class CapturingEmail:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


@pytest.fixture
def emails(monkeypatch: pytest.MonkeyPatch) -> CapturingEmail:
    capture = CapturingEmail()
    monkeypatch.setattr(family_endpoint, "get_email_provider", lambda: capture)
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


def _invite_token(emails: CapturingEmail) -> str:
    body = emails.sent[-1][2]
    return body.split("/invite/")[1].split("\n")[0].strip()


async def _invite_and_join(
    client: AsyncClient, emails: CapturingEmail, role: str = "member"
) -> str:
    """Owner invites the spouse; spouse signs up + accepts. Returns family vault id.
    Leaves the client logged in as the spouse with the family vault selected."""
    resp = await client.post(
        "/api/v1/family/invites", json={"email": SPOUSE["email"], "role": role}
    )
    assert resp.status_code == 201, resp.text
    vault_id = (await client.get("/api/v1/vault/usage")).json()["vault_id"]
    token = _invite_token(emails)

    client.cookies.clear()
    await client.post("/api/v1/auth/signup", json=SPOUSE)
    info = await client.get(f"/api/v1/family/invites/{token}")
    assert info.status_code == 200
    assert info.json()["role"] == role
    accepted = await client.post(f"/api/v1/family/invites/{token}/accept")
    assert accepted.status_code == 204
    client.cookies.set("vaultly_vault", vault_id)
    return vault_id


async def test_invite_accept_and_vault_switch(owner: AsyncClient, emails: CapturingEmail) -> None:
    vault_id = await _invite_and_join(owner, emails)
    # Spouse now sees the family vault via the cookie
    usage = (await owner.get("/api/v1/vault/usage")).json()
    assert usage["vault_id"] == vault_id
    assert usage["member_count"] == 2

    members = (await owner.get("/api/v1/family/members")).json()
    assert len(members["members"]) == 2
    roles = {m["email"]: m["role"] for m in members["members"]}
    assert roles[SIGNUP["email"]] == "owner"
    assert roles[SPOUSE["email"]] == "member"


async def test_invite_cannot_be_reused(owner: AsyncClient, emails: CapturingEmail) -> None:
    await owner.post("/api/v1/family/invites", json={"email": SPOUSE["email"], "role": "member"})
    token = _invite_token(emails)
    owner.cookies.clear()
    await owner.post("/api/v1/auth/signup", json=SPOUSE)
    assert (await owner.post(f"/api/v1/family/invites/{token}/accept")).status_code == 204
    assert (await owner.post(f"/api/v1/family/invites/{token}/accept")).status_code == 404


async def test_member_cannot_invite(owner: AsyncClient, emails: CapturingEmail) -> None:
    await _invite_and_join(owner, emails, role="member")
    resp = await owner.post(
        "/api/v1/family/invites", json={"email": "third@example.com", "role": "member"}
    )
    assert resp.status_code == 403


async def test_owner_changes_role_and_matrix(
    owner: AsyncClient, emails: CapturingEmail, storage: FakeStorage
) -> None:
    doc = await _upload(owner, storage)  # owner's doc, category "other"
    vault_id = await _invite_and_join(owner, emails)

    # Spouse (member) sees the doc by default
    listed = (await owner.get("/api/v1/documents")).json()
    assert [d["id"] for d in listed] == [doc["id"]]

    # Owner locks the "other" category to none for the spouse
    owner.cookies.clear()
    await owner.post(
        "/api/v1/auth/login",
        json={"email": SIGNUP["email"], "password": SIGNUP["password"]},
    )
    members = (await owner.get("/api/v1/family/members")).json()["members"]
    spouse_membership = next(m for m in members if m["email"] == SPOUSE["email"])
    patched = await owner.patch(
        f"/api/v1/family/members/{spouse_membership['membership_id']}",
        json={"category_access": {"other": "none"}},
    )
    assert patched.status_code == 200

    # Spouse can no longer see, download, or search it
    owner.cookies.clear()
    await owner.post(
        "/api/v1/auth/login", json={"email": SPOUSE["email"], "password": SPOUSE["password"]}
    )
    owner.cookies.set("vaultly_vault", vault_id)
    assert (await owner.get("/api/v1/documents")).json() == []
    assert (await owner.get(f"/api/v1/documents/{doc['id']}/download")).status_code == 404
    assert (await owner.get("/api/v1/search", params={"q": "receipt"})).json()["total"] == 0


async def test_view_access_blocks_editing(
    owner: AsyncClient, emails: CapturingEmail, storage: FakeStorage
) -> None:
    doc = await _upload(owner, storage)
    vault_id = await _invite_and_join(owner, emails)

    owner.cookies.clear()
    await owner.post(
        "/api/v1/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}
    )
    members = (await owner.get("/api/v1/family/members")).json()["members"]
    spouse = next(m for m in members if m["email"] == SPOUSE["email"])
    await owner.patch(
        f"/api/v1/family/members/{spouse['membership_id']}",
        json={"category_access": {"other": "view"}},
    )

    owner.cookies.clear()
    await owner.post(
        "/api/v1/auth/login", json={"email": SPOUSE["email"], "password": SPOUSE["password"]}
    )
    owner.cookies.set("vaultly_vault", vault_id)
    # View: list + download OK, delete/edit forbidden
    assert len((await owner.get("/api/v1/documents")).json()) == 1
    assert (await owner.get(f"/api/v1/documents/{doc['id']}/download")).status_code == 200
    assert (await owner.delete(f"/api/v1/documents/{doc['id']}")).status_code == 403
    assert (
        await owner.patch(f"/api/v1/documents/{doc['id']}", json={"title": "x"})
    ).status_code == 403


async def test_owner_cannot_change_self(owner: AsyncClient) -> None:
    members = (await owner.get("/api/v1/family/members")).json()["members"]
    me = members[0]
    resp = await owner.patch(
        f"/api/v1/family/members/{me['membership_id']}", json={"role": "member"}
    )
    assert resp.status_code == 400
