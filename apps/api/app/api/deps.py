from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models import User

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
