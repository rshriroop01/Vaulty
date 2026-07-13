from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models import User, Vault, VaultMembership, VaultRole

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

ACCESS_COOKIE = "vaultly_access"
REFRESH_COOKIE = "vaultly_refresh"


async def get_current_user(
    session: DbSession,
    vaultly_access: Annotated[str | None, Cookie()] = None,
) -> User:
    if vaultly_access is None:
        raise UnauthorizedError("Not authenticated")
    user_id = decode_access_token(vaultly_access)
    if user_id is None:
        raise UnauthorizedError("Invalid or expired session")
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired session")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@dataclass
class VaultContext:
    user: User
    vault: Vault
    role: VaultRole

    @property
    def can_write(self) -> bool:
        # Emergency-only members can never modify the vault (design screen 2i)
        return self.role in (VaultRole.owner, VaultRole.admin, VaultRole.member)


async def get_current_vault(session: DbSession, user: CurrentUser) -> VaultContext:
    """The user's active vault. Single vault per user for now; multi-vault
    switching would extend this with an X-Vault-ID header, not new endpoints."""
    row = (
        await session.execute(
            select(Vault, VaultMembership.role)
            .join(VaultMembership, VaultMembership.vault_id == Vault.id)
            .where(VaultMembership.user_id == user.id)
            .order_by(Vault.created_at)
        )
    ).first()
    if row is None:
        raise ForbiddenError("No vault membership")
    vault, role = row
    return VaultContext(user=user, vault=vault, role=role)


CurrentVault = Annotated[VaultContext, Depends(get_current_vault)]
