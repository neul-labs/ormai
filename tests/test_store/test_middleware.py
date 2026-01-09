"""Tests for audit middleware."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ormai.core.context import Principal, RunContext
from ormai.core.errors import OrmAIError, WriteDisabledError
from ormai.store.base import AuditStore
from ormai.store.middleware import AuditMiddleware
from ormai.store.models import AuditRecord


class MockAuditStore(AuditStore):
    """Mock audit store for testing."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def store(self, record: AuditRecord) -> None:
        self.records.append(record)

    async def get(self, record_id: str) -> AuditRecord | None:
        for r in self.records:
            if r.id == record_id:
                return r
        return None

    async def query(
        self,
        *,
        _tenant_id: str | None = None,
        _principal_id: str | None = None,
        _tool_name: str | None = None,
        _start_time: datetime | None = None,
        _end_time: datetime | None = None,
        limit: int = 100,
        _offset: int = 0,
    ) -> list[AuditRecord]:
        return self.records[:limit]

    async def count(
        self,
        *,
        _tenant_id: str | None = None,
        _principal_id: str | None = None,
        _tool_name: str | None = None,
        _start_time: datetime | None = None,
        _end_time: datetime | None = None,
    ) -> int:
        return len(self.records)


@pytest.fixture
def mock_store() -> MockAuditStore:
    return MockAuditStore()


@pytest.fixture
def ctx() -> RunContext:
    return RunContext(
        principal=Principal(
            tenant_id="tenant-1",
            user_id="user-1",
            roles=["admin"],
        ),
        request_id="req-123",
        trace_id="trace-456",
        now=datetime.now(timezone.utc),
        db=None,
    )


class TestAuditMiddleware:
    """Tests for AuditMiddleware."""

    @pytest.mark.asyncio
    async def test_wrap_async_success(self, mock_store: MockAuditStore, ctx: RunContext):
        """Test wrapping a successful async function."""
        middleware = AuditMiddleware(store=mock_store)

        async def my_tool():
            return {"data": [1, 2, 3]}

        result = await middleware.wrap_async(
            tool_name="my_tool",
            ctx=ctx,
            inputs={"param": "value"},
            fn=my_tool,
        )

        assert result == {"data": [1, 2, 3]}
        assert len(mock_store.records) == 1
        record = mock_store.records[0]
        assert record.tool_name == "my_tool"
        assert record.principal_id == "user-1"
        assert record.tenant_id == "tenant-1"
        assert record.error is None
        assert record.inputs == {"param": "value"}

    @pytest.mark.asyncio
    async def test_wrap_async_error(self, mock_store: MockAuditStore, ctx: RunContext):
        """Test wrapping an async function that raises an error."""
        middleware = AuditMiddleware(store=mock_store)

        async def failing_tool():
            raise OrmAIError("Test error")

        with pytest.raises(OrmAIError):
            await middleware.wrap_async(
                tool_name="failing_tool",
                ctx=ctx,
                inputs={},
                fn=failing_tool,
            )

        assert len(mock_store.records) == 1
        record = mock_store.records[0]
        assert record.error is not None
        assert record.error.code == "ORMAI_ERROR"
        assert record.error.message == "Test error"

    @pytest.mark.asyncio
    async def test_sanitize_inputs(self, mock_store: MockAuditStore, ctx: RunContext):
        """Test that sensitive inputs are sanitized."""
        middleware = AuditMiddleware(store=mock_store, sanitize_inputs=True)

        async def my_tool():
            return {}

        await middleware.wrap_async(
            tool_name="my_tool",
            ctx=ctx,
            inputs={
                "username": "john",
                "password": "secret123",
                "api_key": "key123",
                "data": {"auth_token": "tok123"},
            },
            fn=my_tool,
        )

        record = mock_store.records[0]
        assert record.inputs["username"] == "john"
        assert record.inputs["password"] == "[REDACTED]"
        assert record.inputs["api_key"] == "[REDACTED]"
        assert record.inputs["data"]["auth_token"] == "[REDACTED]"


class TestAuditMiddlewareMutations:
    """Tests for mutation-specific audit functionality."""

    @pytest.mark.asyncio
    async def test_mutation_with_snapshots(self, mock_store: MockAuditStore, ctx: RunContext):
        """Test mutation with before/after snapshots captured."""
        middleware = AuditMiddleware(store=mock_store, capture_snapshots=True)

        class MockResult:
            success = True
            data = {"id": 1, "status": "updated"}

        async def update_fn():
            return MockResult()

        before = {"id": 1, "status": "pending"}

        result = await middleware.wrap_mutation_async(
            tool_name="db.update",
            ctx=ctx,
            inputs={"model": "Order", "id": 1, "data": {"status": "updated"}},
            fn=update_fn,
            before_snapshot=before,
        )

        assert result.success is True
        assert len(mock_store.records) == 1
        record = mock_store.records[0]
        assert record.tool_name == "db.update"
        assert record.before_snapshot == {"id": 1, "status": "pending"}
        assert record.after_snapshot == {"id": 1, "status": "updated"}
        assert record.affected_rows == 1

    @pytest.mark.asyncio
    async def test_mutation_without_snapshots(self, mock_store: MockAuditStore, ctx: RunContext):
        """Test mutation without snapshot capture."""
        middleware = AuditMiddleware(store=mock_store, capture_snapshots=False)

        class MockResult:
            success = True
            data = {"id": 1, "status": "updated"}

        async def update_fn():
            return MockResult()

        await middleware.wrap_mutation_async(
            tool_name="db.update",
            ctx=ctx,
            inputs={"model": "Order", "id": 1},
            fn=update_fn,
            before_snapshot={"id": 1, "status": "pending"},
        )

        record = mock_store.records[0]
        # Snapshots should not be captured when disabled
        assert record.before_snapshot is None
        assert record.after_snapshot is None

    @pytest.mark.asyncio
    async def test_mutation_bulk_update(self, mock_store: MockAuditStore, ctx: RunContext):
        """Test bulk update records affected count."""
        middleware = AuditMiddleware(store=mock_store, capture_snapshots=True)

        class MockBulkResult:
            success = True
            updated_count = 5
            data = None

        async def bulk_update_fn():
            return MockBulkResult()

        await middleware.wrap_mutation_async(
            tool_name="db.bulk_update",
            ctx=ctx,
            inputs={"model": "Order", "ids": [1, 2, 3, 4, 5]},
            fn=bulk_update_fn,
        )

        record = mock_store.records[0]
        assert record.affected_rows == 5

    @pytest.mark.asyncio
    async def test_mutation_error_captured(self, mock_store: MockAuditStore, ctx: RunContext):
        """Test mutation error is captured in audit record."""
        middleware = AuditMiddleware(store=mock_store, capture_snapshots=True)

        async def failing_mutation():
            raise WriteDisabledError(operation="update", model="Order")

        before = {"id": 1, "status": "pending"}

        with pytest.raises(WriteDisabledError):
            await middleware.wrap_mutation_async(
                tool_name="db.update",
                ctx=ctx,
                inputs={"model": "Order", "id": 1},
                fn=failing_mutation,
                before_snapshot=before,
            )

        record = mock_store.records[0]
        assert record.error is not None
        assert record.error.code == "WRITE_DISABLED"
        # Before snapshot should still be captured even on error
        assert record.before_snapshot == before
        assert record.after_snapshot is None

    @pytest.mark.asyncio
    async def test_mutation_sanitizes_inputs(self, mock_store: MockAuditStore, ctx: RunContext):
        """Test mutation sanitizes sensitive data in inputs."""
        middleware = AuditMiddleware(store=mock_store, sanitize_inputs=True)

        class MockResult:
            success = True
            data = None

        async def create_fn():
            return MockResult()

        await middleware.wrap_mutation_async(
            tool_name="db.create",
            ctx=ctx,
            inputs={
                "model": "User",
                "data": {
                    "username": "john",
                    "password_hash": "hash123",
                    "email": "john@example.com",
                },
            },
            fn=create_fn,
        )

        record = mock_store.records[0]
        assert record.inputs["data"]["username"] == "john"
        assert record.inputs["data"]["password_hash"] == "[REDACTED]"
        assert record.inputs["data"]["email"] == "john@example.com"
