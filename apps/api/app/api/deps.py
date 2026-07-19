from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, Request
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


ACCESS_LEVELS = ("full", "view", "none")


@dataclass
class VaultContext:
    user: User
    vault: Vault
    membership: VaultMembership

    @property
    def role(self) -> VaultRole:
        return self.membership.role

    @property
    def can_write(self) -> bool:
        # Emergency-only members can never modify the vault (design screen 2i)
        return self.role in (VaultRole.owner, VaultRole.admin, VaultRole.member)

    def category_access(self, category: str) -> str:
        """Access matrix (screen 2i): owners/admins always full; members default
        full, emergency-only defaults none; explicit matrix entries win."""
        if self.role in (VaultRole.owner, VaultRole.admin):
            return "full"
        default = "none" if self.role == VaultRole.emergency else "full"
        matrix = self.membership.category_access or {}
        value = matrix.get(category, default)
        return value if value in ACCESS_LEVELS else default

    def visible_categories(self) -> list[str] | None:
        """None = unrestricted; otherwise the categories this member may see."""
        from app.models import DocumentCategory

        if self.role in (VaultRole.owner, VaultRole.admin):
            return None
        visible = [c.value for c in DocumentCategory if self.category_access(c.value) != "none"]
        return visible


async def get_current_vault(
    request: Request, session: DbSession, user: CurrentUser
) -> VaultContext:
    """The user's active vault. Selection order: X-Vault-ID header, then the
    vaultly_vault cookie (set by the sidebar switcher), then oldest membership."""
    requested = request.headers.get("X-Vault-ID") or request.cookies.get("vaultly_vault")
    if requested:
        try:
            requested_id = UUID(requested)
        except ValueError:
            requested_id = None
        if requested_id is not None:
            row = (
                await session.execute(
                    select(Vault, VaultMembership)
                    .join(VaultMembership, VaultMembership.vault_id == Vault.id)
                    .where(VaultMembership.user_id == user.id, Vault.id == requested_id)
                )
            ).first()
            if row is not None:
                return VaultContext(user=user, vault=row[0], membership=row[1])
        # Stale cookie for a vault the user left — fall through to the default

    row = (
        await session.execute(
            select(Vault, VaultMembership)
            .join(VaultMembership, VaultMembership.vault_id == Vault.id)
            .where(VaultMembership.user_id == user.id)
            .order_by(Vault.created_at)
        )
    ).first()
    if row is None:
        raise ForbiddenError("No vault membership")
    return VaultContext(user=user, vault=row[0], membership=row[1])


CurrentVault = Annotated[VaultContext, Depends(get_current_vault)]
