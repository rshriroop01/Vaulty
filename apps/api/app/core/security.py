import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()

ACCESS_TOKEN_TYPE = "access"  # noqa: S105 — token *type* label, not a secret


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> UUID | None:
    """Returns the user id, or None for any invalid/expired/mistyped token."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        return None
    try:
        return UUID(payload["sub"])
    except (KeyError, ValueError):
        return None


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Refresh tokens are stored hashed — a DB leak must not yield usable sessions."""
    return hashlib.sha256(token.encode()).hexdigest()
