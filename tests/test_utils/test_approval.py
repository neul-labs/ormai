"""Tests for approval helpers."""

from datetime import datetime, timezone

import pytest

from ormai.core.context import Principal, RunContext
from ormai.core.dsl import CreateRequest, DeleteRequest, UpdateRequest
from ormai.utils.approval import (
    ApprovalRequest,
    ApprovalStatus,
    AutoApproveGate,
    CallbackApprovalGate,
    InMemoryApprovalQueue,
)


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


class TestApprovalRequest:
    """Tests for ApprovalRequest creation."""

    def test_from_create(self, ctx: RunContext):
        """Test creating approval request from CreateRequest."""
        request = CreateRequest(
            model="Order",
            data={"customer_id": 1, "total": 99.99},
            reason="New order",
        )

        approval = ApprovalRequest.from_create(request, ctx)

        assert approval.operation == "create"
        assert approval.model == "Order"
        assert approval.request_data == {"data": {"customer_id": 1, "total": 99.99}}
        assert approval.principal_id == "user-1"
        assert approval.tenant_id == "tenant-1"
        assert approval.reason == "New order"
        assert approval.status == ApprovalStatus.PENDING

    def test_from_update(self, ctx: RunContext):
        """Test creating approval request from UpdateRequest."""
        request = UpdateRequest(
            model="Order",
            id=123,
            data={"status": "shipped"},
            reason="Order shipped",
        )

        approval = ApprovalRequest.from_update(request, ctx)

        assert approval.operation == "update"
        assert approval.model == "Order"
        assert approval.request_data == {"id": 123, "data": {"status": "shipped"}}
        assert approval.reason == "Order shipped"

    def test_from_delete(self, ctx: RunContext):
        """Test creating approval request from DeleteRequest."""
        request = DeleteRequest(
            model="Order",
            id=123,
            reason="Customer cancelled",
            hard=True,
        )

        approval = ApprovalRequest.from_delete(request, ctx)

        assert approval.operation == "delete"
        assert approval.model == "Order"
        assert approval.request_data == {"id": 123, "hard": True}
        assert approval.reason == "Customer cancelled"


class TestAutoApproveGate:
    """Tests for AutoApproveGate."""

    @pytest.mark.asyncio
    async def test_auto_approves(self, ctx: RunContext):
        """Test that auto-approve gate approves all requests."""
        gate = AutoApproveGate()
        request = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )

        decision = await gate.check(request)

        assert decision.approved is True
        assert decision.message == "Auto-approved"

    @pytest.mark.asyncio
    async def test_submit_returns_id(self, ctx: RunContext):
        """Test that submit returns request ID."""
        gate = AutoApproveGate()
        request = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )

        request_id = await gate.submit(request)

        assert request_id == request.id

    @pytest.mark.asyncio
    async def test_get_status_returns_none(self):
        """Test that get_status returns None for auto-approve."""
        gate = AutoApproveGate()

        status = await gate.get_status("any-id")

        assert status is None


class TestCallbackApprovalGate:
    """Tests for CallbackApprovalGate."""

    @pytest.mark.asyncio
    async def test_callback_approve(self, ctx: RunContext):
        """Test callback that approves."""
        gate = CallbackApprovalGate(callback=lambda r: True)
        request = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )

        decision = await gate.check(request)

        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_callback_reject(self, ctx: RunContext):
        """Test callback that rejects."""
        gate = CallbackApprovalGate(
            callback=lambda r: False,
            rejection_message="Not allowed",
        )
        request = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )

        decision = await gate.check(request)

        assert decision.approved is False
        assert decision.message == "Not allowed"

    @pytest.mark.asyncio
    async def test_callback_with_logic(self, ctx: RunContext):
        """Test callback with conditional logic."""

        def approve_only_orders(request: ApprovalRequest) -> bool:
            return request.model == "Order"

        gate = CallbackApprovalGate(callback=approve_only_orders)

        # Order should be approved
        order_request = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )
        assert (await gate.check(order_request)).approved is True

        # Customer should be rejected
        customer_request = ApprovalRequest.from_create(
            CreateRequest(model="Customer", data={"x": 1}), ctx
        )
        assert (await gate.check(customer_request)).approved is False


class TestInMemoryApprovalQueue:
    """Tests for InMemoryApprovalQueue."""

    @pytest.mark.asyncio
    async def test_submit_and_check_pending(self, ctx: RunContext):
        """Test submitting a request and checking pending status."""
        queue = InMemoryApprovalQueue()
        request = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )

        # Submit request
        request_id = await queue.submit(request)
        assert request_id == request.id

        # Check should return not approved with request_id
        decision = await queue.check(request)
        assert decision.approved is False
        assert decision.request_id == request.id
        assert decision.message == "Awaiting approval"

    @pytest.mark.asyncio
    async def test_approve_request(self, ctx: RunContext):
        """Test approving a pending request."""
        queue = InMemoryApprovalQueue()
        request = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )

        await queue.submit(request)

        # Approve
        result = queue.approve(request.id, decided_by="admin")
        assert result is True

        # Now check should return approved
        decision = await queue.check(request)
        assert decision.approved is True

        # Verify status
        status = await queue.get_status(request.id)
        assert status.status == ApprovalStatus.APPROVED
        assert status.decided_by == "admin"

    @pytest.mark.asyncio
    async def test_reject_request(self, ctx: RunContext):
        """Test rejecting a pending request."""
        queue = InMemoryApprovalQueue()
        request = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )

        await queue.submit(request)

        # Reject
        result = queue.reject(request.id, reason="Not authorized", decided_by="admin")
        assert result is True

        # Check should return rejected
        decision = await queue.check(request)
        assert decision.approved is False
        assert decision.message == "Not authorized"

        # Verify status
        status = await queue.get_status(request.id)
        assert status.status == ApprovalStatus.REJECTED
        assert status.rejection_reason == "Not authorized"

    @pytest.mark.asyncio
    async def test_pending_requests(self, ctx: RunContext):
        """Test getting pending requests."""
        queue = InMemoryApprovalQueue()

        # Submit multiple requests
        req1 = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )
        req2 = ApprovalRequest.from_create(
            CreateRequest(model="Customer", data={"x": 1}), ctx
        )

        await queue.submit(req1)
        await queue.submit(req2)

        # Both should be pending
        pending = queue.pending_requests()
        assert len(pending) == 2

        # Approve one
        queue.approve(req1.id)

        # Only one should be pending now
        pending = queue.pending_requests()
        assert len(pending) == 1
        assert pending[0].id == req2.id

    @pytest.mark.asyncio
    async def test_approve_non_existent(self):
        """Test approving non-existent request returns False."""
        queue = InMemoryApprovalQueue()

        result = queue.approve("non-existent")

        assert result is False

    @pytest.mark.asyncio
    async def test_approve_already_approved(self, ctx: RunContext):
        """Test approving already approved request returns False."""
        queue = InMemoryApprovalQueue()
        request = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )

        await queue.submit(request)
        queue.approve(request.id)

        # Second approval should fail
        result = queue.approve(request.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_queue(self, ctx: RunContext):
        """Test clearing the queue."""
        queue = InMemoryApprovalQueue()
        request = ApprovalRequest.from_create(
            CreateRequest(model="Order", data={"x": 1}), ctx
        )

        await queue.submit(request)
        assert len(queue.pending_requests()) == 1

        queue.clear()
        assert len(queue.pending_requests()) == 0
