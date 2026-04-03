"""
Rate limiting middleware for OrmAI.

Provides request-level rate limiting based on tenant, user, or custom keys.
Supports sliding window algorithm with configurable limits.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ormai.core.context import Principal


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        limit: int,
        window_seconds: int,
        retry_after: float,
    ) -> None:
        super().__init__(message)
        self.limit = limit
        self.window_seconds = window_seconds
        self.retry_after = retry_after


@dataclass
class RateLimitConfig:
    """
    Configuration for rate limiting.

    Attributes:
        requests_per_minute: Maximum requests per minute per key
        requests_per_hour: Maximum requests per hour per key
        burst_limit: Maximum burst of requests in a short window (10 seconds)
        key_prefix: Prefix for rate limit keys (for namespacing)
    """

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    key_prefix: str = "ormai"

    def __post_init__(self) -> None:
        if self.requests_per_minute < 1:
            raise ValueError("requests_per_minute must be at least 1")
        if self.requests_per_hour < self.requests_per_minute:
            raise ValueError("requests_per_hour must be >= requests_per_minute")
        if self.burst_limit < 1:
            raise ValueError("burst_limit must be at least 1")


class RateLimitBackend(ABC):
    """
    Abstract backend for rate limit storage.

    Backends must be thread-safe and support atomic increment operations.
    """

    @abstractmethod
    async def increment(self, key: str, window_seconds: int) -> int:
        """
        Increment counter for key within the given window.

        Args:
            key: Rate limit key (e.g., "tenant:acme:minute")
            window_seconds: Window duration in seconds

        Returns:
            Current count after increment
        """
        ...

    @abstractmethod
    async def get_count(self, key: str) -> int:
        """
        Get current count for key.

        Args:
            key: Rate limit key

        Returns:
            Current count (0 if key doesn't exist)
        """
        ...

    @abstractmethod
    async def reset(self, key: str) -> None:
        """
        Reset counter for key.

        Args:
            key: Rate limit key to reset
        """
        ...


@dataclass
class _WindowEntry:
    """Entry for tracking requests in a time window."""

    count: int = 0
    expires_at: float = 0.0


class InMemoryBackend(RateLimitBackend):
    """
    In-memory rate limit backend using sliding window.

    Suitable for single-instance deployments or development.
    For distributed deployments, use Redis or a similar backend.
    """

    def __init__(self) -> None:
        self._windows: dict[str, _WindowEntry] = {}
        self._lock = asyncio.Lock()

    async def increment(self, key: str, window_seconds: int) -> int:
        async with self._lock:
            now = time.time()
            entry = self._windows.get(key)

            if entry is None or now >= entry.expires_at:
                # Start new window
                self._windows[key] = _WindowEntry(
                    count=1,
                    expires_at=now + window_seconds,
                )
                return 1
            else:
                # Increment existing window
                entry.count += 1
                return entry.count

    async def get_count(self, key: str) -> int:
        async with self._lock:
            now = time.time()
            entry = self._windows.get(key)
            if entry is None or now >= entry.expires_at:
                return 0
            return entry.count

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._windows.pop(key, None)

    async def cleanup_expired(self) -> int:
        """
        Remove expired entries to prevent memory leaks.

        Returns:
            Number of entries cleaned up
        """
        async with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._windows.items() if now >= entry.expires_at
            ]
            for key in expired_keys:
                del self._windows[key]
            return len(expired_keys)


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    current_count: int
    limit: int
    window_seconds: int
    retry_after: float = 0.0
    key: str = ""


class RateLimiter:
    """
    Rate limiter for OrmAI requests.

    Supports multiple rate limit windows (minute, hour, burst) and can limit
    by tenant, user, or custom keys.

    Usage:
        limiter = RateLimiter(
            config=RateLimitConfig(requests_per_minute=60),
            backend=InMemoryBackend(),
        )

        # Check rate limit for a principal
        result = await limiter.check(principal)
        if not result.allowed:
            raise RateLimitError(...)

        # Or use check_and_raise which raises automatically
        await limiter.check_and_raise(principal)
    """

    def __init__(
        self,
        config: RateLimitConfig | None = None,
        backend: RateLimitBackend | None = None,
    ) -> None:
        self.config = config or RateLimitConfig()
        self.backend = backend or InMemoryBackend()

    def _build_key(self, principal: Principal, window: str) -> str:
        """Build rate limit key for principal and window."""
        return f"{self.config.key_prefix}:tenant:{principal.tenant_id}:user:{principal.user_id}:{window}"

    def _build_tenant_key(self, principal: Principal, window: str) -> str:
        """Build rate limit key for tenant (shared across all users)."""
        return f"{self.config.key_prefix}:tenant:{principal.tenant_id}:{window}"

    async def check(
        self,
        principal: Principal,
        tool_name: str | None = None,  # noqa: ARG002 - reserved for tool-specific limits
    ) -> RateLimitResult:
        """
        Check if request is allowed under rate limits.

        Checks burst, minute, and hour limits in order of strictness.

        Args:
            principal: The principal making the request
            tool_name: Optional tool name for tool-specific limits

        Returns:
            RateLimitResult indicating if request is allowed
        """
        # Check burst limit (10 second window)
        burst_key = self._build_key(principal, "burst")
        burst_count = await self.backend.increment(burst_key, 10)
        if burst_count > self.config.burst_limit:
            return RateLimitResult(
                allowed=False,
                current_count=burst_count,
                limit=self.config.burst_limit,
                window_seconds=10,
                retry_after=1.0,
                key=burst_key,
            )

        # Check minute limit
        minute_key = self._build_key(principal, "minute")
        minute_count = await self.backend.increment(minute_key, 60)
        if minute_count > self.config.requests_per_minute:
            return RateLimitResult(
                allowed=False,
                current_count=minute_count,
                limit=self.config.requests_per_minute,
                window_seconds=60,
                retry_after=60.0 - (time.time() % 60),
                key=minute_key,
            )

        # Check hour limit
        hour_key = self._build_key(principal, "hour")
        hour_count = await self.backend.increment(hour_key, 3600)
        if hour_count > self.config.requests_per_hour:
            return RateLimitResult(
                allowed=False,
                current_count=hour_count,
                limit=self.config.requests_per_hour,
                window_seconds=3600,
                retry_after=3600.0 - (time.time() % 3600),
                key=hour_key,
            )

        return RateLimitResult(
            allowed=True,
            current_count=minute_count,
            limit=self.config.requests_per_minute,
            window_seconds=60,
            key=minute_key,
        )

    async def check_and_raise(
        self,
        principal: Principal,
        tool_name: str | None = None,
    ) -> RateLimitResult:
        """
        Check rate limit and raise RateLimitError if exceeded.

        Args:
            principal: The principal making the request
            tool_name: Optional tool name for tool-specific limits

        Returns:
            RateLimitResult if allowed

        Raises:
            RateLimitError: If rate limit is exceeded
        """
        result = await self.check(principal, tool_name)
        if not result.allowed:
            raise RateLimitError(
                f"Rate limit exceeded: {result.current_count}/{result.limit} "
                f"requests in {result.window_seconds}s window. "
                f"Retry after {result.retry_after:.1f}s.",
                limit=result.limit,
                window_seconds=result.window_seconds,
                retry_after=result.retry_after,
            )
        return result

    async def get_status(self, principal: Principal) -> dict[str, RateLimitResult]:
        """
        Get current rate limit status for a principal.

        Returns:
            Dict mapping window names to their current status
        """
        status = {}

        burst_key = self._build_key(principal, "burst")
        burst_count = await self.backend.get_count(burst_key)
        status["burst"] = RateLimitResult(
            allowed=burst_count <= self.config.burst_limit,
            current_count=burst_count,
            limit=self.config.burst_limit,
            window_seconds=10,
            key=burst_key,
        )

        minute_key = self._build_key(principal, "minute")
        minute_count = await self.backend.get_count(minute_key)
        status["minute"] = RateLimitResult(
            allowed=minute_count <= self.config.requests_per_minute,
            current_count=minute_count,
            limit=self.config.requests_per_minute,
            window_seconds=60,
            key=minute_key,
        )

        hour_key = self._build_key(principal, "hour")
        hour_count = await self.backend.get_count(hour_key)
        status["hour"] = RateLimitResult(
            allowed=hour_count <= self.config.requests_per_hour,
            current_count=hour_count,
            limit=self.config.requests_per_hour,
            window_seconds=3600,
            key=hour_key,
        )

        return status


# Convenience function to create a rate limiter with defaults
def create_rate_limiter(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_limit: int = 10,
) -> RateLimiter:
    """
    Create a rate limiter with in-memory backend.

    Args:
        requests_per_minute: Maximum requests per minute
        requests_per_hour: Maximum requests per hour
        burst_limit: Maximum burst requests in 10 seconds

    Returns:
        Configured RateLimiter instance
    """
    return RateLimiter(
        config=RateLimitConfig(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            burst_limit=burst_limit,
        ),
        backend=InMemoryBackend(),
    )
