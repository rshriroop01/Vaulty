"""Redis-backed fixed-window rate limiting (M10 hardening).

Mirrors the provider pattern used across the app (app/services/billing.py,
app/services/assistant.py, app/services/email.py): a `Protocol` wrapping the
real backend, injected via a module-level `get_*` factory so route handlers
never talk to Redis directly and tests can swap in `FakeRateLimiter`.

Fail-open by design: if Redis is unreachable, `RedisRateLimiter.check` logs a
warning and reports the request as allowed. Availability beats strictness for
an abuse guard — a Redis outage should degrade to "no rate limiting", not
"nobody can log in".

Disabled by default in the test environment (`rate_limiting_enabled`) so the
hundreds of requests a test suite fires don't trip the same fixed-window
counters; a test that wants to exercise the limiter overrides
`rate_limiting_enabled` to return True and supplies `FakeRateLimiter` via
`get_rate_limiter`.
"""

import time
from dataclasses import dataclass
from typing import Annotated, Protocol

import redis.asyncio as aioredis
import structlog
from fastapi import Depends, Request

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.errors import RateLimitedError

logger = structlog.get_logger("rate_limit")

WINDOW_SECONDS = 60


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int  # seconds until the caller can retry


class RateLimiter(Protocol):
    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult: ...


_client: aioredis.Redis | None = None  # lazy, shared connection pool


def _get_client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(  # type: ignore[no-untyped-call]
            get_settings().redis_url, decode_responses=True
        )
    return _client


class RedisRateLimiter:
    """Fixed-window counter via INCR + EXPIRE, keyed on `key:<window index>`.
    Not perfectly smooth at window boundaries (a client could fire `limit`
    requests right before and right after a boundary), but cheap — one round
    trip on the common path — and simple enough to reason about for an abuse
    guard. A sliding-window log isn't worth the extra Redis calls here."""

    def __init__(self) -> None:
        self._client = _get_client()

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        try:
            window_index = int(time.time()) // window_seconds
            redis_key = f"ratelimit:{key}:{window_index}"
            count = await self._client.incr(redis_key)
            if count == 1:
                await self._client.expire(redis_key, window_seconds)
            return RateLimitResult(
                allowed=count <= limit,
                remaining=max(0, limit - count),
                retry_after=window_seconds - (int(time.time()) % window_seconds),
            )
        except Exception:
            logger.warning("rate_limit_backend_unreachable", key=key)
            return RateLimitResult(allowed=True, remaining=limit, retry_after=0)


class FakeRateLimiter:
    """In-memory limiter for tests: same fixed-window semantics as
    `RedisRateLimiter`, keyed off `time.time()` so tests can advance the
    window by monkeypatching `app.core.rate_limit.time.time`. Set
    `raise_on_check = True` to exercise a caller's fail-open handling — this
    fake itself never fails open (that behavior belongs to
    `RedisRateLimiter`, and is unit-tested directly against it)."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        window_index = int(time.time()) // window_seconds
        redis_key = f"{key}:{window_index}"
        count = self._counts.get(redis_key, 0) + 1
        self._counts[redis_key] = count
        return RateLimitResult(
            allowed=count <= limit,
            remaining=max(0, limit - count),
            retry_after=window_seconds - (int(time.time()) % window_seconds),
        )


def get_rate_limiter() -> RateLimiter:
    return RedisRateLimiter()


def rate_limiting_enabled() -> bool:
    """Overridden in tests that specifically exercise the limiter."""
    return get_settings().environment != "test"


LimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
EnabledDep = Annotated[bool, Depends(rate_limiting_enabled)]


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _enforce(enabled: bool, limiter: RateLimiter, name: str, key: str, limit: int) -> None:
    if not enabled:
        return
    result = await limiter.check(f"{name}:{key}", limit, WINDOW_SECONDS)
    if not result.allowed:
        logger.info("rate_limited", bucket=name, key=key)
        raise RateLimitedError(
            f"Too many requests — try again in {result.retry_after}s.",
            retry_after=result.retry_after,
        )


async def rate_limit_login(request: Request, limiter: LimiterDep, enabled: EnabledDep) -> None:
    """10/min per IP — brute-force guard on the login endpoint."""
    settings = get_settings()
    await _enforce(
        enabled, limiter, "auth_login", _client_ip(request), settings.rate_limit_auth_per_minute
    )


async def rate_limit_signup(request: Request, limiter: LimiterDep, enabled: EnabledDep) -> None:
    """10/min per IP — abuse guard on account creation."""
    settings = get_settings()
    await _enforce(
        enabled, limiter, "auth_signup", _client_ip(request), settings.rate_limit_auth_per_minute
    )


async def rate_limit_assistant(
    request: Request, limiter: LimiterDep, enabled: EnabledDep, user: CurrentUser
) -> None:
    """20/min per user — cost/abuse guard on the Claude-backed assistant."""
    settings = get_settings()
    await _enforce(
        enabled, limiter, "assistant_ask", str(user.id), settings.rate_limit_assistant_per_minute
    )


async def rate_limit_emergency(
    request: Request, token: str, limiter: LimiterDep, enabled: EnabledDep
) -> None:
    """5/min per IP+token — PIN brute-force guard on the public emergency-binder
    endpoint (no auth cookie; `token` is the path parameter FastAPI already
    resolves for the route, reused here by name)."""
    settings = get_settings()
    key = f"{_client_ip(request)}:{token}"
    await _enforce(
        enabled, limiter, "emergency_access", key, settings.rate_limit_emergency_per_minute
    )
