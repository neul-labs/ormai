"""
Transaction helpers with retry and rollback strategies.

Provides utilities for executing database operations with automatic
retry handling for transient failures.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryableError(Exception):
    """Base class for errors that should trigger a retry."""

    pass


class TransientDatabaseError(RetryableError):
    """Transient database error that may succeed on retry."""

    pass


class DeadlockError(RetryableError):
    """Deadlock detected, retry with backoff."""

    pass


class ConnectionError(RetryableError):
    """Database connection error, retry after reconnect."""

    pass


class RetryStrategy(str, Enum):
    """Retry strategy types."""

    NONE = "none"  # No retries
    FIXED = "fixed"  # Fixed delay between retries
    EXPONENTIAL = "exponential"  # Exponential backoff
    EXPONENTIAL_JITTER = "exponential_jitter"  # Exponential with random jitter


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    # Retry strategy
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER

    # Maximum number of retry attempts
    max_retries: int = 3

    # Base delay between retries (seconds)
    base_delay: float = 0.1

    # Maximum delay between retries (seconds)
    max_delay: float = 5.0

    # Jitter factor (0.0 to 1.0) for randomization
    jitter: float = 0.25

    # Exception types that should trigger retry
    retryable_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (RetryableError,)
    )

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        if self.strategy == RetryStrategy.NONE:
            return 0

        if self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay

        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (2 ** attempt)

        elif self.strategy == RetryStrategy.EXPONENTIAL_JITTER:
            delay = self.base_delay * (2 ** attempt)
            jitter_range = delay * self.jitter
            delay = delay + random.uniform(-jitter_range, jitter_range)

        else:
            delay = self.base_delay

        return min(delay, self.max_delay)


# Preset configurations
RETRY_NONE = RetryConfig(strategy=RetryStrategy.NONE, max_retries=0)
RETRY_FAST = RetryConfig(
    strategy=RetryStrategy.EXPONENTIAL_JITTER,
    max_retries=3,
    base_delay=0.05,
    max_delay=1.0,
)
RETRY_STANDARD = RetryConfig(
    strategy=RetryStrategy.EXPONENTIAL_JITTER,
    max_retries=5,
    base_delay=0.1,
    max_delay=5.0,
)
RETRY_PERSISTENT = RetryConfig(
    strategy=RetryStrategy.EXPONENTIAL_JITTER,
    max_retries=10,
    base_delay=0.2,
    max_delay=30.0,
)


@dataclass
class RetryResult:
    """Result of a retried operation."""

    success: bool
    result: Any = None
    attempts: int = 0
    last_error: Exception | None = None
    errors: list[Exception] = field(default_factory=list)


async def retry_async(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    config: RetryConfig = RETRY_STANDARD,
    on_retry: Callable[[int, Exception], None] | None = None,
    **kwargs: Any,
) -> T:
    """
    Execute an async function with retry logic.

    Args:
        fn: The async function to execute
        *args: Positional arguments for fn
        config: Retry configuration
        on_retry: Optional callback called before each retry with (attempt, error)
        **kwargs: Keyword arguments for fn

    Returns:
        The result of the function

    Raises:
        The last exception if all retries are exhausted
    """
    last_error: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await fn(*args, **kwargs)

        except config.retryable_exceptions as e:
            last_error = e

            if attempt >= config.max_retries:
                logger.warning(
                    f"Retry exhausted after {attempt + 1} attempts: {e}"
                )
                raise

            delay = config.get_delay(attempt)
            logger.debug(
                f"Retry attempt {attempt + 1}/{config.max_retries} "
                f"after {delay:.2f}s due to: {e}"
            )

            if on_retry:
                on_retry(attempt, e)

            await asyncio.sleep(delay)

    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Retry logic error")


def retry_sync(
    fn: Callable[..., T],
    *args: Any,
    config: RetryConfig = RETRY_STANDARD,
    on_retry: Callable[[int, Exception], None] | None = None,
    **kwargs: Any,
) -> T:
    """
    Execute a sync function with retry logic.

    Args:
        fn: The function to execute
        *args: Positional arguments for fn
        config: Retry configuration
        on_retry: Optional callback called before each retry with (attempt, error)
        **kwargs: Keyword arguments for fn

    Returns:
        The result of the function

    Raises:
        The last exception if all retries are exhausted
    """
    import time

    last_error: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return fn(*args, **kwargs)

        except config.retryable_exceptions as e:
            last_error = e

            if attempt >= config.max_retries:
                logger.warning(
                    f"Retry exhausted after {attempt + 1} attempts: {e}"
                )
                raise

            delay = config.get_delay(attempt)
            logger.debug(
                f"Retry attempt {attempt + 1}/{config.max_retries} "
                f"after {delay:.2f}s due to: {e}"
            )

            if on_retry:
                on_retry(attempt, e)

            time.sleep(delay)

    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Retry logic error")


class TransactionManager:
    """
    Manager for database transactions with retry support.

    Wraps database operations in transactions with automatic
    retry for transient failures.

    Usage:
        manager = TransactionManager(session_factory, config=RETRY_STANDARD)

        result = await manager.execute(async_operation_fn)
    """

    def __init__(
        self,
        session_factory: Callable[[], Any],
        config: RetryConfig = RETRY_STANDARD,
    ) -> None:
        """
        Initialize the transaction manager.

        Args:
            session_factory: Callable that creates a new database session
            config: Retry configuration
        """
        self.session_factory = session_factory
        self.config = config

    async def execute_async(
        self,
        fn: Callable[[Any], Awaitable[T]],
        on_retry: Callable[[int, Exception], None] | None = None,
    ) -> T:
        """
        Execute an async operation in a transaction with retry.

        The function receives a session and should perform its operations.
        The session is committed on success or rolled back on failure.

        Args:
            fn: Async function that receives session and returns result
            on_retry: Optional callback for retry events

        Returns:
            The result of the operation
        """

        async def wrapped() -> T:
            session = self.session_factory()
            try:
                result = await fn(session)
                if hasattr(session, "commit"):
                    if asyncio.iscoroutinefunction(session.commit):
                        await session.commit()
                    else:
                        session.commit()
                return result
            except Exception:
                if hasattr(session, "rollback"):
                    if asyncio.iscoroutinefunction(session.rollback):
                        await session.rollback()
                    else:
                        session.rollback()
                raise
            finally:
                if hasattr(session, "close"):
                    if asyncio.iscoroutinefunction(session.close):
                        await session.close()
                    else:
                        session.close()

        return await retry_async(wrapped, config=self.config, on_retry=on_retry)

    def execute_sync(
        self,
        fn: Callable[[Any], T],
        on_retry: Callable[[int, Exception], None] | None = None,
    ) -> T:
        """
        Execute a sync operation in a transaction with retry.

        Args:
            fn: Function that receives session and returns result
            on_retry: Optional callback for retry events

        Returns:
            The result of the operation
        """

        def wrapped() -> T:
            session = self.session_factory()
            try:
                result = fn(session)
                if hasattr(session, "commit"):
                    session.commit()
                return result
            except Exception:
                if hasattr(session, "rollback"):
                    session.rollback()
                raise
            finally:
                if hasattr(session, "close"):
                    session.close()

        return retry_sync(wrapped, config=self.config, on_retry=on_retry)


def with_retry(
    config: RetryConfig = RETRY_STANDARD,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator for adding retry logic to async functions.

    Usage:
        @with_retry(RETRY_FAST)
        async def my_database_operation():
            ...
    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await retry_async(fn, *args, config=config, **kwargs)

        return wrapper

    return decorator


def with_retry_sync(
    config: RetryConfig = RETRY_STANDARD,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for adding retry logic to sync functions.

    Usage:
        @with_retry_sync(RETRY_FAST)
        def my_database_operation():
            ...
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return retry_sync(fn, *args, config=config, **kwargs)

        return wrapper

    return decorator
