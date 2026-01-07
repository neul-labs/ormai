"""
Approval helpers for human-in-the-loop write operations.

Provides pluggable approval gates that can block, queue, or conditionally
approve write operations before execution.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from ormai.core.context import RunContext
from ormai.core.dsl import (
    BulkUpdateRequest,
    CreateRequest,
    DeleteRequest,
    UpdateRequest,
)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """
    A request for approval of a write operation.

    Contains all information needed to review and approve/reject the operation.
    """

    # Unique identifier
    id: str = field(default_factory=lambda: str(uuid4()))

    # Operation details
    operation: str = ""  # "create", "update", "delete", "bulk_update"
    model: str = ""
    request_data: dict[str, Any] = field(default_factory=dict)

    # Context
    principal_id: str = ""
    tenant_id: str = ""
    reason: str | None = None

    # Status
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    decided_by: str | None = None
    rejection_reason: str | None = None

    @classmethod
    def from_create(cls, request: CreateRequest, ctx: RunContext) -> "ApprovalRequest":
        """Create an approval request from a CreateRequest."""
        return cls(
            operation="create",
            model=request.model,
            request_data={"data": request.data},
            principal_id=ctx.principal.user_id,
            tenant_id=ctx.principal.tenant_id,
            reason=request.reason,
        )

    @classmethod
    def from_update(cls, request: UpdateRequest, ctx: RunContext) -> "ApprovalRequest":
        """Create an approval request from an UpdateRequest."""
        return cls(
            operation="update",
            model=request.model,
            request_data={"id": request.id, "data": request.data},
            principal_id=ctx.principal.user_id,
            tenant_id=ctx.principal.tenant_id,
            reason=request.reason,
        )

    @classmethod
    def from_delete(cls, request: DeleteRequest, ctx: RunContext) -> "ApprovalRequest":
        """Create an approval request from a DeleteRequest."""
        return cls(
            operation="delete",
            model=request.model,
            request_data={"id": request.id, "hard": request.hard},
            principal_id=ctx.principal.user_id,
            tenant_id=ctx.principal.tenant_id,
            reason=request.reason,
        )

    @classmethod
    def from_bulk_update(
        cls, request: BulkUpdateRequest, ctx: RunContext
    ) -> "ApprovalRequest":
        """Create an approval request from a BulkUpdateRequest."""
        return cls(
            operation="bulk_update",
            model=request.model,
            request_data={"ids": request.ids, "data": request.data},
            principal_id=ctx.principal.user_id,
            tenant_id=ctx.principal.tenant_id,
            reason=request.reason,
        )


@dataclass
class ApprovalDecision:
    """Result of an approval check."""

    approved: bool
    request_id: str | None = None
    message: str | None = None


class ApprovalGate(ABC):
    """
    Abstract base class for approval gates.

    Approval gates determine whether a write operation can proceed,
    needs to be queued for approval, or should be rejected.
    """

    @abstractmethod
    async def check(
        self,
        request: ApprovalRequest,
    ) -> ApprovalDecision:
        """
        Check if an operation is approved.

        Returns:
            ApprovalDecision indicating whether to proceed, wait, or reject.
        """
        ...

    @abstractmethod
    async def submit(
        self,
        request: ApprovalRequest,
    ) -> str:
        """
        Submit a request for approval.

        Returns:
            The approval request ID for tracking.
        """
        ...

    @abstractmethod
    async def get_status(self, request_id: str) -> ApprovalRequest | None:
        """
        Get the status of an approval request.

        Returns:
            The approval request with current status, or None if not found.
        """
        ...


class AutoApproveGate(ApprovalGate):
    """
    Approval gate that automatically approves all requests.

    Useful for development/testing or when approval is handled externally.
    """

    async def check(self, request: ApprovalRequest) -> ApprovalDecision:  # noqa: ARG002
        """Auto-approve all requests."""
        return ApprovalDecision(approved=True, message="Auto-approved")

    async def submit(self, request: ApprovalRequest) -> str:
        """Submit returns immediately with approved status."""
        return request.id

    async def get_status(self, request_id: str) -> ApprovalRequest | None:  # noqa: ARG002
        """Always returns None as we don't track auto-approved requests."""
        return None


class CallbackApprovalGate(ApprovalGate):
    """
    Approval gate that uses a synchronous callback for decisions.

    The callback receives the approval request and returns True/False.
    Useful for simple approval logic or integration with external systems.
    """

    def __init__(
        self,
        callback: Callable[[ApprovalRequest], bool],
        rejection_message: str = "Request rejected by approval callback",
    ) -> None:
        """
        Initialize with a callback function.

        Args:
            callback: Function that receives ApprovalRequest and returns bool
            rejection_message: Message to include when request is rejected
        """
        self.callback = callback
        self.rejection_message = rejection_message

    async def check(self, request: ApprovalRequest) -> ApprovalDecision:
        """Check approval via callback."""
        approved = self.callback(request)
        return ApprovalDecision(
            approved=approved,
            message=None if approved else self.rejection_message,
        )

    async def submit(self, request: ApprovalRequest) -> str:
        """Submit is same as check for callback gate."""
        return request.id

    async def get_status(self, request_id: str) -> ApprovalRequest | None:  # noqa: ARG002
        """Callback gate doesn't track requests."""
        return None


class InMemoryApprovalQueue(ApprovalGate):
    """
    In-memory approval queue for development and testing.

    Requests are queued and can be approved/rejected via the queue methods.
    Not suitable for production use (not persistent, not distributed).
    """

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    async def check(self, request: ApprovalRequest) -> ApprovalDecision:
        """
        Check if the request is already approved.

        Returns approved=False with request_id if pending approval.
        """
        existing = self._requests.get(request.id)
        if existing is None:
            return ApprovalDecision(
                approved=False,
                request_id=request.id,
                message="Approval required",
            )

        if existing.status == ApprovalStatus.APPROVED:
            return ApprovalDecision(approved=True)
        elif existing.status == ApprovalStatus.REJECTED:
            return ApprovalDecision(
                approved=False,
                message=existing.rejection_reason or "Request rejected",
            )
        else:
            return ApprovalDecision(
                approved=False,
                request_id=request.id,
                message="Awaiting approval",
            )

    async def submit(self, request: ApprovalRequest) -> str:
        """Add request to the queue."""
        self._requests[request.id] = request
        return request.id

    async def get_status(self, request_id: str) -> ApprovalRequest | None:
        """Get request status."""
        return self._requests.get(request_id)

    # Queue management methods

    def pending_requests(self) -> list[ApprovalRequest]:
        """Get all pending requests."""
        return [
            r for r in self._requests.values() if r.status == ApprovalStatus.PENDING
        ]

    def approve(self, request_id: str, decided_by: str = "system") -> bool:
        """
        Approve a pending request.

        Returns True if request was found and approved.
        """
        request = self._requests.get(request_id)
        if request is None or request.status != ApprovalStatus.PENDING:
            return False

        # Create new request with updated status (dataclass is immutable by default)
        self._requests[request_id] = ApprovalRequest(
            id=request.id,
            operation=request.operation,
            model=request.model,
            request_data=request.request_data,
            principal_id=request.principal_id,
            tenant_id=request.tenant_id,
            reason=request.reason,
            status=ApprovalStatus.APPROVED,
            created_at=request.created_at,
            decided_at=datetime.now(timezone.utc),
            decided_by=decided_by,
        )
        return True

    def reject(
        self,
        request_id: str,
        reason: str = "Rejected",
        decided_by: str = "system",
    ) -> bool:
        """
        Reject a pending request.

        Returns True if request was found and rejected.
        """
        request = self._requests.get(request_id)
        if request is None or request.status != ApprovalStatus.PENDING:
            return False

        self._requests[request_id] = ApprovalRequest(
            id=request.id,
            operation=request.operation,
            model=request.model,
            request_data=request.request_data,
            principal_id=request.principal_id,
            tenant_id=request.tenant_id,
            reason=request.reason,
            status=ApprovalStatus.REJECTED,
            created_at=request.created_at,
            decided_at=datetime.now(timezone.utc),
            decided_by=decided_by,
            rejection_reason=reason,
        )
        return True

    def clear(self) -> None:
        """Clear all requests."""
        self._requests.clear()
