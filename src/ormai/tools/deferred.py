"""
Deferred tool execution pattern for human-in-the-loop approvals.

Provides a wrapper that intercepts mutation tools and routes them through
an approval gate before execution.
"""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from ormai.core.context import RunContext
from ormai.core.dsl import (
    BulkUpdateRequest,
    BulkUpdateResult,
    CreateRequest,
    CreateResult,
    DeleteRequest,
    DeleteResult,
    UpdateRequest,
    UpdateResult,
)
from ormai.core.errors import WriteApprovalRequiredError
from ormai.utils.approval import ApprovalGate, ApprovalRequest, ApprovalStatus

T = TypeVar("T", bound=BaseModel)


@dataclass
class DeferredResult(Generic[T]):
    """
    Result of a deferred operation.

    Either contains the actual result (if approved and executed),
    or an approval request ID (if pending approval).
    """

    # Whether the operation was executed
    executed: bool

    # The result if executed
    result: T | None = None

    # Approval request ID if pending
    approval_id: str | None = None

    # Status message
    message: str | None = None


class DeferredExecutor:
    """
    Executor that defers mutations through an approval gate.

    Usage:
        gate = InMemoryApprovalQueue()
        executor = DeferredExecutor(gate)

        # Wrap a mutation tool
        result = await executor.execute_create(
            request=CreateRequest(...),
            ctx=ctx,
            execute_fn=lambda: adapter.execute_create(...),
        )

        if not result.executed:
            # Operation is pending approval
            print(f"Approval required: {result.approval_id}")
    """

    def __init__(self, gate: ApprovalGate) -> None:
        """
        Initialize with an approval gate.

        Args:
            gate: The approval gate to use for decisions
        """
        self.gate = gate

    async def execute_create(
        self,
        request: CreateRequest,
        ctx: RunContext,
        execute_fn: Any,
    ) -> DeferredResult[CreateResult]:
        """
        Execute a create operation through the approval gate.

        Args:
            request: The create request
            ctx: Run context
            execute_fn: Async function to execute if approved

        Returns:
            DeferredResult containing either the result or approval ID
        """
        approval_request = ApprovalRequest.from_create(request, ctx)
        return await self._execute_with_approval(
            approval_request, execute_fn, CreateResult
        )

    async def execute_update(
        self,
        request: UpdateRequest,
        ctx: RunContext,
        execute_fn: Any,
    ) -> DeferredResult[UpdateResult]:
        """Execute an update operation through the approval gate."""
        approval_request = ApprovalRequest.from_update(request, ctx)
        return await self._execute_with_approval(
            approval_request, execute_fn, UpdateResult
        )

    async def execute_delete(
        self,
        request: DeleteRequest,
        ctx: RunContext,
        execute_fn: Any,
    ) -> DeferredResult[DeleteResult]:
        """Execute a delete operation through the approval gate."""
        approval_request = ApprovalRequest.from_delete(request, ctx)
        return await self._execute_with_approval(
            approval_request, execute_fn, DeleteResult
        )

    async def execute_bulk_update(
        self,
        request: BulkUpdateRequest,
        ctx: RunContext,
        execute_fn: Any,
    ) -> DeferredResult[BulkUpdateResult]:
        """Execute a bulk update operation through the approval gate."""
        approval_request = ApprovalRequest.from_bulk_update(request, ctx)
        return await self._execute_with_approval(
            approval_request, execute_fn, BulkUpdateResult
        )

    async def _execute_with_approval(
        self,
        approval_request: ApprovalRequest,
        execute_fn: Any,
        result_type: type[T],
    ) -> DeferredResult[T]:
        """Execute an operation through the approval gate."""
        # Check approval status
        decision = await self.gate.check(approval_request)

        if decision.approved:
            # Execute the operation
            result = await execute_fn()
            return DeferredResult(
                executed=True,
                result=result,
                message="Operation executed",
            )

        # Not approved - submit for approval if not already submitted
        status = await self.gate.get_status(approval_request.id)
        if status is None:
            await self.gate.submit(approval_request)

        return DeferredResult(
            executed=False,
            approval_id=approval_request.id,
            message=decision.message or "Awaiting approval",
        )

    async def check_and_execute(
        self,
        approval_id: str,
        execute_fn: Any,
    ) -> DeferredResult[Any]:
        """
        Check if a pending operation is now approved and execute if so.

        Use this to resume execution after approval is granted.

        Args:
            approval_id: The approval request ID
            execute_fn: Async function to execute if approved

        Returns:
            DeferredResult with execution status
        """
        status = await self.gate.get_status(approval_id)

        if status is None:
            return DeferredResult(
                executed=False,
                message="Approval request not found",
            )

        if status.status == ApprovalStatus.APPROVED:
            result = await execute_fn()
            return DeferredResult(
                executed=True,
                result=result,
                message="Operation executed after approval",
            )

        if status.status == ApprovalStatus.REJECTED:
            return DeferredResult(
                executed=False,
                message=f"Operation rejected: {status.rejection_reason}",
            )

        return DeferredResult(
            executed=False,
            approval_id=approval_id,
            message="Still awaiting approval",
        )


def require_approval_or_raise(
    request: CreateRequest | UpdateRequest | DeleteRequest | BulkUpdateRequest,
    ctx: RunContext,
    approval_id: str | None = None,
) -> None:
    """
    Raise WriteApprovalRequiredError for operations requiring approval.

    Use this in tool implementations to signal that approval is needed.

    Args:
        request: The mutation request
        ctx: Run context
        approval_id: Optional approval ID if already submitted

    Raises:
        WriteApprovalRequiredError: Always raises to signal approval needed
    """
    if isinstance(request, CreateRequest):
        operation = "create"
        model = request.model
    elif isinstance(request, UpdateRequest):
        operation = "update"
        model = request.model
    elif isinstance(request, DeleteRequest):
        operation = "delete"
        model = request.model
    elif isinstance(request, BulkUpdateRequest):
        operation = "bulk_update"
        model = request.model
    else:
        operation = "unknown"
        model = "unknown"

    raise WriteApprovalRequiredError(
        operation=operation,
        model=model,
        approval_id=approval_id,
    )
