"""Tests for deferred tool execution."""

from datetime import datetime, timezone

import pytest

from ormai.core.context import Principal, RunContext
from ormai.core.dsl import CreateRequest, CreateResult, UpdateRequest, UpdateResult
from ormai.core.errors import WriteApprovalRequiredError
from ormai.tools.deferred import DeferredExecutor, require_approval_or_raise
from ormai.utils.approval import AutoApproveGate, InMemoryApprovalQueue


@pytest.fixture
def ctx() -> RunContext:
    return RunContext(
        principal=Principal(
            tenant_id="tenant-1",
            user_id="user-1",
            roles=["admin"],
        ),
        request_id="req-123",
        now=datetime.now(timezone.utc),
        db=None,
    )


class TestDeferredExecutor:
    """Tests for DeferredExecutor."""

    @pytest.mark.asyncio
    async def test_auto_approve_executes_immediately(self, ctx: RunContext):
        """Test that auto-approve gate executes immediately."""
        gate = AutoApproveGate()
        executor = DeferredExecutor(gate)

        request = CreateRequest(model="Order", data={"x": 1})

        async def execute_fn():
            return CreateResult(data={"id": 1, "x": 1}, id=1, success=True)

        result = await executor.execute_create(request, ctx, execute_fn)

        assert result.executed is True
        assert result.result is not None
        assert result.result.id == 1
        assert result.approval_id is None

    @pytest.mark.asyncio
    async def test_queue_defers_execution(self, ctx: RunContext):
        """Test that queue gate defers execution."""
        queue = InMemoryApprovalQueue()
        executor = DeferredExecutor(queue)

        request = CreateRequest(model="Order", data={"x": 1})

        async def execute_fn():
            return CreateResult(data={"id": 1, "x": 1}, id=1, success=True)

        result = await executor.execute_create(request, ctx, execute_fn)

        assert result.executed is False
        assert result.approval_id is not None
        assert result.result is None
        assert "approval" in result.message.lower()

    @pytest.mark.asyncio
    async def test_queue_executes_after_approval(self, ctx: RunContext):
        """Test that execution proceeds after approval."""
        queue = InMemoryApprovalQueue()
        executor = DeferredExecutor(queue)

        request = CreateRequest(model="Order", data={"x": 1})
        executed_count = 0

        async def execute_fn():
            nonlocal executed_count
            executed_count += 1
            return CreateResult(data={"id": 1, "x": 1}, id=1, success=True)

        # First attempt - should be deferred
        result1 = await executor.execute_create(request, ctx, execute_fn)
        assert result1.executed is False
        assert executed_count == 0

        # Approve the request
        queue.approve(result1.approval_id)

        # Check and execute
        result2 = await executor.check_and_execute(result1.approval_id, execute_fn)
        assert result2.executed is True
        assert executed_count == 1
        assert result2.result.id == 1

    @pytest.mark.asyncio
    async def test_queue_rejects_execution(self, ctx: RunContext):
        """Test handling of rejected requests."""
        queue = InMemoryApprovalQueue()
        executor = DeferredExecutor(queue)

        request = CreateRequest(model="Order", data={"x": 1})

        async def execute_fn():
            return CreateResult(data={"id": 1, "x": 1}, id=1, success=True)

        # First attempt - should be deferred
        result1 = await executor.execute_create(request, ctx, execute_fn)
        assert result1.executed is False

        # Reject the request
        queue.reject(result1.approval_id, reason="Not authorized")

        # Check status
        result2 = await executor.check_and_execute(result1.approval_id, execute_fn)
        assert result2.executed is False
        assert "rejected" in result2.message.lower()
        assert "Not authorized" in result2.message

    @pytest.mark.asyncio
    async def test_update_deferred(self, ctx: RunContext):
        """Test update operation through deferred executor."""
        queue = InMemoryApprovalQueue()
        executor = DeferredExecutor(queue)

        request = UpdateRequest(model="Order", id=1, data={"status": "shipped"})

        async def execute_fn():
            return UpdateResult(data={"id": 1, "status": "shipped"}, success=True, found=True)

        result = await executor.execute_update(request, ctx, execute_fn)

        assert result.executed is False
        assert result.approval_id is not None

        # Verify the pending request has correct operation type
        pending = queue.pending_requests()
        assert len(pending) == 1
        assert pending[0].operation == "update"

    @pytest.mark.asyncio
    async def test_check_nonexistent_approval(self, _ctx: RunContext):
        """Test checking a non-existent approval ID."""
        queue = InMemoryApprovalQueue()
        executor = DeferredExecutor(queue)

        async def execute_fn():
            return CreateResult(data={"id": 1}, id=1, success=True)

        result = await executor.check_and_execute("non-existent", execute_fn)

        assert result.executed is False
        assert "not found" in result.message.lower()


class TestRequireApprovalOrRaise:
    """Tests for require_approval_or_raise helper."""

    def test_raises_for_create(self, ctx: RunContext):
        """Test that it raises for create requests."""
        request = CreateRequest(model="Order", data={"x": 1})

        with pytest.raises(WriteApprovalRequiredError) as exc_info:
            require_approval_or_raise(request, ctx)

        assert exc_info.value.code == "WRITE_APPROVAL_REQUIRED"
        assert "create" in str(exc_info.value.message).lower()
        assert "Order" in str(exc_info.value.message)

    def test_raises_for_update(self, ctx: RunContext):
        """Test that it raises for update requests."""
        request = UpdateRequest(model="Customer", id=1, data={"x": 1})

        with pytest.raises(WriteApprovalRequiredError) as exc_info:
            require_approval_or_raise(request, ctx)

        assert "update" in str(exc_info.value.message).lower()
        assert "Customer" in str(exc_info.value.message)

    def test_includes_approval_id(self, ctx: RunContext):
        """Test that approval ID is included in error."""
        request = CreateRequest(model="Order", data={"x": 1})

        with pytest.raises(WriteApprovalRequiredError) as exc_info:
            require_approval_or_raise(request, ctx, approval_id="approval-123")

        assert exc_info.value.details.get("approval_id") == "approval-123"
