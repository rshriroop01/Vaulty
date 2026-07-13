from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feature_flag import FeatureFlag


async def is_enabled(session: AsyncSession, key: str, *, default: bool = False) -> bool:
    """Look up a feature flag; unknown flags fall back to `default` (off)."""
    flag = await session.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
    return flag.enabled if flag is not None else default
