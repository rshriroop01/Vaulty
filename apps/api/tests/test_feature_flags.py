from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.feature_flags import is_enabled
from app.models import AuditLog, FeatureFlag


class FakeSession:
    """Stands in for AsyncSession — feature-flag lookup is a single scalar select."""

    def __init__(self, result: FeatureFlag | None) -> None:
        self._result = result

    async def scalar(self, _stmt: Any) -> FeatureFlag | None:
        return self._result


async def test_enabled_flag() -> None:
    session = FakeSession(FeatureFlag(key="gmail_sync", enabled=True))
    assert await is_enabled(cast(AsyncSession, session), "gmail_sync") is True


async def test_disabled_flag() -> None:
    session = FakeSession(FeatureFlag(key="gmail_sync", enabled=False))
    assert await is_enabled(cast(AsyncSession, session), "gmail_sync") is False


async def test_unknown_flag_defaults_off() -> None:
    session = FakeSession(None)
    assert await is_enabled(cast(AsyncSession, session), "nope") is False
    assert await is_enabled(cast(AsyncSession, session), "nope", default=True) is True


def test_audit_log_model_definition() -> None:
    entry = AuditLog(action="document.upload", context={"size": 123})
    assert entry.action == "document.upload"
    assert AuditLog.__tablename__ == "audit_log"
    assert FeatureFlag.__tablename__ == "feature_flags"
