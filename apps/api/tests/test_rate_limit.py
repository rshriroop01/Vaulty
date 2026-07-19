"""M10 hardening: Redis-backed fixed-window rate limiting.

Covers, per the M10 scope: over-limit -> 429 in the RFC 7807 shape, window
reset, fail-open when Redis is unreachable, and the disabled-by-default
behavior in the test environment (tests/conftest.py pins ENVIRONMENT=test).
"""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

import app.core.rate_limit as rate_limit_module
from app.core.errors import PROBLEM_CONTENT_TYPE
from app.core.rate_limit import (
    FakeRateLimiter,
    RedisRateLimiter,
    get_rate_limiter,
    rate_limiting_enabled,
)

LOGIN_PAYLOAD = {"email": "nobody@example.com", "password": "wrong-pass-1"}


class _BrokenRedisClient:
    """Stands in for a Redis client that can't be reached."""

    async def incr(self, key: str) -> int:
        raise ConnectionError("redis unreachable")


async def test_redis_rate_limiter_fails_open_when_redis_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit_module, "_get_client", lambda: _BrokenRedisClient())
    limiter = RedisRateLimiter()

    result = await limiter.check("some-key", limit=1, window_seconds=60)

    assert result.allowed is True


async def test_fake_rate_limiter_blocks_once_over_limit() -> None:
    limiter = FakeRateLimiter()
    for _ in range(3):
        result = await limiter.check("k", limit=3, window_seconds=60)
        assert result.allowed is True

    blocked = await limiter.check("k", limit=3, window_seconds=60)

    assert blocked.allowed is False
    assert blocked.retry_after > 0


async def test_fake_rate_limiter_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    base = 1_700_000_000
    monkeypatch.setattr(rate_limit_module.time, "time", lambda: base)
    limiter = FakeRateLimiter()
    for _ in range(2):
        assert (await limiter.check("k", limit=2, window_seconds=60)).allowed is True
    assert (await limiter.check("k", limit=2, window_seconds=60)).allowed is False

    # Jump forward past the 60s window — the counter starts fresh.
    monkeypatch.setattr(rate_limit_module.time, "time", lambda: base + 61)

    result = await limiter.check("k", limit=2, window_seconds=60)

    assert result.allowed is True


async def test_rate_limiting_disabled_by_default_in_test_env(client: AsyncClient) -> None:
    """No dependency override -> rate_limiting_enabled() reads settings.environment,
    which tests/conftest.py pins to "test", so this never trips even well past
    the configured 10/min login limit."""
    statuses = []
    for _ in range(15):
        resp = await client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD)
        statuses.append(resp.status_code)

    assert all(status == 401 for status in statuses)


async def test_login_rate_limited_when_enabled(app: FastAPI, client: AsyncClient) -> None:
    # The override must return the SAME instance every call — a fresh
    # FakeRateLimiter() per request would reset the counter each time.
    fake = FakeRateLimiter()
    app.dependency_overrides[rate_limiting_enabled] = lambda: True
    app.dependency_overrides[get_rate_limiter] = lambda: fake

    responses = [await client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD) for _ in range(11)]

    allowed = responses[:10]
    blocked = responses[10]
    assert all(r.status_code == 401 for r in allowed)  # wrong password, but not rate-limited
    assert blocked.status_code == 429
    assert blocked.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    body = blocked.json()
    assert body["title"] == "Too Many Requests"
    assert body["type"] == "https://vaultly.app/problems/rate-limited"
    assert "request_id" in body
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) > 0


async def test_signup_and_login_have_independent_buckets(app: FastAPI, client: AsyncClient) -> None:
    """Separate limiter keys (auth_login vs auth_signup) — exhausting one
    doesn't affect the other, even though both share the same per-IP limit."""
    fake = FakeRateLimiter()
    app.dependency_overrides[rate_limiting_enabled] = lambda: True
    app.dependency_overrides[get_rate_limiter] = lambda: fake

    for _ in range(10):
        resp = await client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD)
        assert resp.status_code == 401
    blocked = await client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD)
    assert blocked.status_code == 429

    # Signup bucket is untouched by the login attempts above.
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"name": "New User", "email": "new@example.com", "password": "new-pass-1"},
    )
    assert signup.status_code == 201
