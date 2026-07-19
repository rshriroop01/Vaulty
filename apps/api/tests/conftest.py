import os
from collections.abc import AsyncIterator

# Must land before any app import touches Settings (get_settings is lru_cache'd
# process-wide): the whole suite runs as ENVIRONMENT=test, which is what
# app/core/rate_limit.py checks to disable rate limiting by default (M10
# hardening) — tests that specifically exercise the limiter opt back in via
# dependency overrides (see tests/test_rate_limit.py).
os.environ.setdefault("ENVIRONMENT", "test")

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_db_session  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
async def app() -> AsyncIterator[FastAPI]:
    """App wired to a fresh in-memory SQLite DB (portable column types keep the
    models compatible; Postgres-only behavior is covered in CI's service tests)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    application = create_app()

    async def _test_session() -> AsyncIterator:
        async with factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = _test_session
    yield application
    await engine.dispose()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
