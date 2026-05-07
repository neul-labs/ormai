"""Tests for rate limiting middleware."""


import pytest

from ormai.core.context import Principal
from ormai.middleware.rate_limit import (
    InMemoryBackend,
    RateLimitConfig,
    RateLimiter,
    RateLimitError,
    RateLimitResult,
    create_rate_limiter,
)


class TestRateLimitConfig:
    def test_defaults(self):
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_limit == 10
        assert config.key_prefix == "ormai"

    def test_custom_values(self):
        config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_hour=2000,
            burst_limit=20,
            key_prefix="test",
        )
        assert config.requests_per_minute == 100
        assert config.requests_per_hour == 2000
        assert config.burst_limit == 20
        assert config.key_prefix == "test"

    def test_invalid_requests_per_minute(self):
        with pytest.raises(ValueError, match="requests_per_minute"):
            RateLimitConfig(requests_per_minute=0)

    def test_invalid_burst_limit(self):
        with pytest.raises(ValueError, match="burst_limit"):
            RateLimitConfig(burst_limit=0)

    def test_hour_less_than_minute(self):
        with pytest.raises(ValueError, match="requests_per_hour"):
            RateLimitConfig(requests_per_minute=100, requests_per_hour=50)


class TestRateLimitError:
    def test_error_attributes(self):
        err = RateLimitError(
            "Rate limit exceeded",
            limit=10,
            window_seconds=60,
            retry_after=30.5,
        )
        assert str(err) == "Rate limit exceeded"
        assert err.limit == 10
        assert err.window_seconds == 60
        assert err.retry_after == 30.5


class TestInMemoryBackend:
    @pytest.mark.asyncio
    async def test_increment_new_key(self):
        backend = InMemoryBackend()
        count = await backend.increment("test:minute", 60)
        assert count == 1

    @pytest.mark.asyncio
    async def test_increment_existing_key(self):
        backend = InMemoryBackend()
        await backend.increment("test:minute", 60)
        count = await backend.increment("test:minute", 60)
        assert count == 2

    @pytest.mark.asyncio
    async def test_increment_expired_window_resets(self):
        backend = InMemoryBackend()
        count = await backend.increment("test:minute", 0)
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_count_missing_key(self):
        backend = InMemoryBackend()
        count = await backend.get_count("nonexistent")
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_count_active_key(self):
        backend = InMemoryBackend()
        await backend.increment("test:minute", 60)
        count = await backend.get_count("test:minute")
        assert count == 1

    @pytest.mark.asyncio
    async def test_reset_key(self):
        backend = InMemoryBackend()
        await backend.increment("test:minute", 60)
        await backend.reset("test:minute")
        count = await backend.get_count("test:minute")
        assert count == 0

    @pytest.mark.asyncio
    async def test_reset_nonexistent_key(self):
        backend = InMemoryBackend()
        await backend.reset("nonexistent")

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        backend = InMemoryBackend()
        await backend.increment("expired:1", 0)
        await backend.increment("active:1", 60)
        cleaned = await backend.cleanup_expired()
        assert cleaned == 1
        assert await backend.get_count("active:1") == 1


class TestRateLimitResult:
    def test_allowed_result(self):
        result = RateLimitResult(
            allowed=True,
            current_count=5,
            limit=10,
            window_seconds=60,
        )
        assert result.allowed is True
        assert result.retry_after == 0.0

    def test_denied_result(self):
        result = RateLimitResult(
            allowed=False,
            current_count=11,
            limit=10,
            window_seconds=60,
            retry_after=30.0,
        )
        assert result.allowed is False


class TestRateLimiter:
    @pytest.fixture
    def principal(self):
        return Principal(tenant_id="tenant-1", user_id="user-1")

    @pytest.fixture
    def limiter(self):
        config = RateLimitConfig(
            requests_per_minute=5,
            requests_per_hour=100,
            burst_limit=3,
        )
        return RateLimiter(config=config, backend=InMemoryBackend())

    def test_build_key(self, limiter, principal):
        key = limiter._build_key(principal, "minute")
        assert key == "ormai:tenant:tenant-1:user:user-1:minute"

    def test_build_tenant_key(self, limiter, principal):
        key = limiter._build_tenant_key(principal, "hour")
        assert key == "ormai:tenant:tenant-1:hour"

    @pytest.mark.asyncio
    async def test_check_allowed(self, limiter, principal):
        result = await limiter.check(principal)
        assert result.allowed is True
        assert result.current_count == 1

    @pytest.mark.asyncio
    async def test_check_burst_exceeded(self, limiter, principal):
        for _ in range(3):
            await limiter.check(principal)
        result = await limiter.check(principal)
        assert result.allowed is False
        assert result.limit == 3
        assert result.window_seconds == 10

    @pytest.mark.asyncio
    async def test_check_minute_exceeded(self, principal):
        config = RateLimitConfig(
            requests_per_minute=5,
            requests_per_hour=100,
            burst_limit=100,
        )
        limiter = RateLimiter(config=config, backend=InMemoryBackend())

        for _ in range(5):
            await limiter.check(principal)
        result = await limiter.check(principal)
        assert result.allowed is False
        assert result.limit == 5

    @pytest.mark.asyncio
    async def test_check_and_raise_allowed(self, limiter, principal):
        result = await limiter.check_and_raise(principal)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_and_raise_raises(self, limiter, principal):
        for _ in range(3):
            await limiter.check_and_raise(principal)

        with pytest.raises(RateLimitError) as exc_info:
            await limiter.check_and_raise(principal)

        assert exc_info.value.limit == 3
        assert exc_info.value.window_seconds == 10

    @pytest.mark.asyncio
    async def test_get_status(self, limiter, principal):
        await limiter.check(principal)
        status = await limiter.get_status(principal)
        assert "burst" in status
        assert "minute" in status
        assert "hour" in status
        assert status["burst"].current_count >= 1


class TestCreateRateLimiter:
    def test_creates_with_defaults(self):
        limiter = create_rate_limiter()
        assert limiter.config.requests_per_minute == 60
        assert limiter.config.requests_per_hour == 1000
        assert limiter.config.burst_limit == 10

    def test_creates_with_custom_values(self):
        limiter = create_rate_limiter(
            requests_per_minute=30,
            requests_per_hour=500,
            burst_limit=5,
        )
        assert limiter.config.requests_per_minute == 30
