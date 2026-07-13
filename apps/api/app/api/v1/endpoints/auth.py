from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Cookie, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select

from app.api.deps import ACCESS_COOKIE, REFRESH_COOKIE, CurrentUser, DbSession
from app.core import audit
from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.models import User, UserSession, Vault, VaultMembership, VaultPlan, VaultRole

router = APIRouter()
logger = structlog.get_logger("auth")


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_rules(cls, v: str) -> str:
        # Mirrored in the sign-up UI (screen 2a password rules)
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VaultSummary(BaseModel):
    id: UUID
    name: str
    plan: str
    role: str


class MeResponse(BaseModel):
    id: UUID
    email: str
    name: str
    vaults: list[VaultSummary]


def _set_auth_cookies(response: Response, user_id: UUID, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token(user_id),
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_ttl_days * 86400,
        path=f"{settings.api_v1_prefix}/auth",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


async def _open_session(db: DbSession, user_id: UUID) -> str:
    token = new_refresh_token()
    db.add(
        UserSession(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_ttl_days),
        )
    )
    return token


async def _me(db: DbSession, user: User) -> MeResponse:
    rows = (
        await db.execute(
            select(Vault, VaultMembership.role)
            .join(VaultMembership, VaultMembership.vault_id == Vault.id)
            .where(VaultMembership.user_id == user.id)
        )
    ).all()
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        vaults=[
            VaultSummary(id=v.id, name=v.name, plan=v.plan.value, role=role.value)
            for v, role in rows
        ],
    )


@router.post("/signup", response_model=MeResponse, status_code=201)
async def signup(body: SignupRequest, db: DbSession, response: Response) -> MeResponse:
    email = body.email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise ConflictError("An account with this email already exists")

    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()

    vault = Vault(name=f"{body.name.split()[0]}'s Vault", plan=VaultPlan.free)
    db.add(vault)
    await db.flush()
    db.add(VaultMembership(vault_id=vault.id, user_id=user.id, role=VaultRole.owner))

    await audit.record(db, "auth.signup", actor_id=user.id, entity_type="user", entity_id=user.id)
    refresh = await _open_session(db, user.id)
    await db.commit()

    _set_auth_cookies(response, user.id, refresh)
    return await _me(db, user)


@router.post("/login", response_model=MeResponse)
async def login(body: LoginRequest, db: DbSession, response: Response) -> MeResponse:
    email = body.email.lower()
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        # Audit the failure but never reveal which half was wrong
        await audit.record(db, "auth.failed_login", email=email)
        await db.commit()
        raise UnauthorizedError("Incorrect email or password")
    if not user.is_active:
        raise UnauthorizedError("This account is disabled")

    await audit.record(db, "auth.login", actor_id=user.id, entity_type="user", entity_id=user.id)
    refresh = await _open_session(db, user.id)
    await db.commit()

    _set_auth_cookies(response, user.id, refresh)
    return await _me(db, user)


@router.post("/refresh", response_model=MeResponse)
async def refresh(
    db: DbSession,
    response: Response,
    vaultly_refresh: Annotated[str | None, Cookie()] = None,
) -> MeResponse:
    if vaultly_refresh is None:
        raise UnauthorizedError("No refresh token")
    now = datetime.now(UTC)
    sess = await db.scalar(
        select(UserSession).where(
            UserSession.refresh_token_hash == hash_refresh_token(vaultly_refresh)
        )
    )
    if sess is None or sess.revoked_at is not None or sess.expires_at.replace(tzinfo=UTC) < now:
        raise UnauthorizedError("Session expired")
    user = await db.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Session expired")

    # Rotate: revoke the presented token, issue a fresh one
    sess.revoked_at = now
    new_token = await _open_session(db, user.id)
    await db.commit()

    _set_auth_cookies(response, user.id, new_token)
    return await _me(db, user)


@router.post("/logout", status_code=204)
async def logout(
    db: DbSession,
    response: Response,
    vaultly_refresh: Annotated[str | None, Cookie()] = None,
) -> None:
    if vaultly_refresh is not None:
        sess = await db.scalar(
            select(UserSession).where(
                UserSession.refresh_token_hash == hash_refresh_token(vaultly_refresh)
            )
        )
        if sess is not None and sess.revoked_at is None:
            sess.revoked_at = datetime.now(UTC)
            await audit.record(db, "auth.logout", actor_id=sess.user_id)
            await db.commit()
    settings = get_settings()
    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE, path=f"{settings.api_v1_prefix}/auth")


@router.get("/me", response_model=MeResponse)
async def me(db: DbSession, user: CurrentUser) -> MeResponse:
    return await _me(db, user)
