"""Liveness and readiness endpoints (mounted at the app root, outside API versioning)."""

import asyncio

import redis.asyncio as aioredis
from fastapi import APIRouter, Response
from sqlalchemy import text

from app.core.config import get_settings

router = APIRouter(tags=["health"])

CHECK_TIMEOUT_SECONDS = 2.0


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness: the process is up and serving requests."""
    return {"status": "ok"}


async def _check_database() -> bool:
    from app.db.session import engine

    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    client = aioredis.from_url(get_settings().redis_url)  # type: ignore[no-untyped-call]
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            await client.ping()
        return True
    except Exception:
        return False
    finally:
        await client.aclose()


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, object]:
    """Readiness: all critical dependencies are reachable."""
    db_ok, redis_ok = await asyncio.gather(_check_database(), _check_redis())
    ready = db_ok and redis_ok
    if not ready:
        response.status_code = 503
    return {
        "status": "ready" if ready else "degraded",
        "checks": {"database": db_ok, "redis": redis_ok},
    }
