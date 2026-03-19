"""Tests for transaction retry helpers."""

import pytest

from ormai.utils.transaction import (
    RETRY_FAST,
    RETRY_NONE,
    RETRY_STANDARD,
    RetryConfig,
    RetryStrategy,
    RetryableError,
    TransactionManager,
    retry_async,
    retry_sync,
    with_retry,
    with_retry_sync,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_fixed_delay(self):
        """Test fixed delay strategy."""
        config = RetryConfig(
            strategy=RetryStrategy.FIXED,
            base_delay=0.5,
        )

        # All attempts should have same delay
        assert config.get_delay(0) == 0.5
        assert config.get_delay(1) == 0.5
        assert config.get_delay(5) == 0.5

    def test_exponential_delay(self):
        """Test exponential delay strategy."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=0.1,
            max_delay=10.0,
        )

        assert config.get_delay(0) == 0.1  # 0.1 * 2^0
        assert config.get_delay(1) == 0.2  # 0.1 * 2^1
        assert config.get_delay(2) == 0.4  # 0.1 * 2^2
        assert config.get_delay(3) == 0.8  # 0.1 * 2^3

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=0.1,
            max_delay=1.0,
        )

        # At attempt 10: 0.1 * 2^10 = 102.4, should be capped at 1.0
        assert config.get_delay(10) == 1.0

    def test_exponential_jitter_varies(self):
        """Test that jitter adds variation."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_JITTER,
            base_delay=1.0,
            jitter=0.5,
        )

        # Get multiple delays and verify they vary
        delays = [config.get_delay(1) for _ in range(10)]

        # All should be around 2.0 (1.0 * 2^1) but with jitter
        for d in delays:
            assert 1.0 <= d <= 3.0  # Within jitter range

        # At least some should be different (statistically very likely)
        assert len(set(delays)) > 1

    def test_none_strategy(self):
        """Test that none strategy returns 0."""
        config = RetryConfig(strategy=RetryStrategy.NONE)

        assert config.get_delay(0) == 0
        assert config.get_delay(5) == 0


class TestRetryAsync:
    """Tests for retry_async."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Test successful operation doesn't retry."""
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_async(operation, config=RETRY_STANDARD)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self):
        """Test that retryable errors trigger retry."""
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("transient failure")
            return "success"

        config = RetryConfig(
            strategy=RetryStrategy.NONE,  # No delay for testing
            max_retries=5,
            retryable_exceptions=(RetryableError,),
        )

        result = await retry_async(operation, config=config)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries(self):
        """Test that exhausted retries raise the error."""
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            raise RetryableError("always fails")

        config = RetryConfig(
            strategy=RetryStrategy.NONE,
            max_retries=3,
            retryable_exceptions=(RetryableError,),
        )

        with pytest.raises(RetryableError):
            await retry_async(operation, config=config)

        assert call_count == 4  # Initial + 3 retries

    @pytest.mark.asyncio
    async def test_non_retryable_error_not_retried(self):
        """Test that non-retryable errors are not retried."""
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        config = RetryConfig(
            strategy=RetryStrategy.NONE,
            max_retries=3,
            retryable_exceptions=(RetryableError,),
        )

        with pytest.raises(ValueError):
            await retry_async(operation, config=config)

        assert call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Test that on_retry callback is called."""
        retry_events = []

        async def operation():
            if len(retry_events) < 2:
                raise RetryableError("fail")
            return "success"

        def on_retry(attempt, error):
            retry_events.append((attempt, str(error)))

        config = RetryConfig(
            strategy=RetryStrategy.NONE,
            max_retries=5,
            retryable_exceptions=(RetryableError,),
        )

        await retry_async(operation, config=config, on_retry=on_retry)

        assert len(retry_events) == 2


class TestRetrySync:
    """Tests for retry_sync."""

    def test_success_no_retry(self):
        """Test successful sync operation."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = retry_sync(operation, config=RETRY_NONE)

        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure(self):
        """Test sync retry on failure."""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("fail once")
            return "success"

        config = RetryConfig(
            strategy=RetryStrategy.NONE,
            max_retries=3,
            retryable_exceptions=(RetryableError,),
        )

        result = retry_sync(operation, config=config)

        assert result == "success"
        assert call_count == 2


class TestDecorators:
    """Tests for retry decorators."""

    @pytest.mark.asyncio
    async def test_with_retry_decorator(self):
        """Test @with_retry decorator."""
        call_count = 0

        @with_retry(RetryConfig(
            strategy=RetryStrategy.NONE,
            max_retries=3,
            retryable_exceptions=(RetryableError,),
        ))
        async def my_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("fail")
            return "done"

        result = await my_operation()

        assert result == "done"
        assert call_count == 2

    def test_with_retry_sync_decorator(self):
        """Test @with_retry_sync decorator."""
        call_count = 0

        @with_retry_sync(RetryConfig(
            strategy=RetryStrategy.NONE,
            max_retries=3,
            retryable_exceptions=(RetryableError,),
        ))
        def my_sync_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("fail")
            return "done"

        result = my_sync_operation()

        assert result == "done"
        assert call_count == 2


class TestTransactionManager:
    """Tests for TransactionManager."""

    @pytest.mark.asyncio
    async def test_async_commit_on_success(self):
        """Test that session is committed on success."""
        commits = []
        rollbacks = []
        closes = []

        class MockSession:
            def commit(self):
                commits.append(1)

            def rollback(self):
                rollbacks.append(1)

            def close(self):
                closes.append(1)

        manager = TransactionManager(
            session_factory=MockSession,
            config=RETRY_NONE,
        )

        async def operation(session):
            return "result"

        result = await manager.execute_async(operation)

        assert result == "result"
        assert len(commits) == 1
        assert len(rollbacks) == 0
        assert len(closes) == 1

    @pytest.mark.asyncio
    async def test_async_rollback_on_error(self):
        """Test that session is rolled back on error."""
        commits = []
        rollbacks = []
        closes = []

        class MockSession:
            def commit(self):
                commits.append(1)

            def rollback(self):
                rollbacks.append(1)

            def close(self):
                closes.append(1)

        manager = TransactionManager(
            session_factory=MockSession,
            config=RETRY_NONE,
        )

        async def operation(session):
            raise ValueError("oops")

        with pytest.raises(ValueError):
            await manager.execute_async(operation)

        assert len(commits) == 0
        assert len(rollbacks) == 1
        assert len(closes) == 1

    def test_sync_execution(self):
        """Test sync transaction execution."""
        commits = []

        class MockSession:
            def commit(self):
                commits.append(1)

            def rollback(self):
                pass

            def close(self):
                pass

        manager = TransactionManager(
            session_factory=MockSession,
            config=RETRY_NONE,
        )

        def operation(session):
            return "sync result"

        result = manager.execute_sync(operation)

        assert result == "sync result"
        assert len(commits) == 1
