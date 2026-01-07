"""
Execution context for OrmAI tool calls.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as SqlAlchemySession


@dataclass(frozen=True)
class Principal:
    """
    Represents the authenticated user/tenant making a request.

    This is the identity that policies are evaluated against for scoping,
    ACL checks, and audit logging.
    """

    tenant_id: str
    user_id: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_role(self, role: str) -> bool:
        """Check if the principal has a specific role."""
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        """Check if the principal has any of the specified roles."""
        return bool(set(roles) & set(self.roles))


@dataclass(frozen=True)
class RunContext:
    """
    Execution context for a single tool call.

    Carries all the information needed to execute a tool call safely:
    - Principal identity for scoping and ACLs
    - Request tracking for auditing
    - Database session for the operation
    - Timing information

    Note: RunContext is immutable. Use the with_* methods to create modified copies.
    """

    principal: Principal
    db: "SqlAlchemySession | Any"  # Database session (SQLAlchemy Session, Tortoise connection, etc.)
    request_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str | None = None
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        user_id: str,
        db: Any,
        roles: tuple[str, ...] | list[str] = (),
        request_id: str | None = None,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "RunContext":
        """
        Convenience factory for creating a RunContext.

        Args:
            tenant_id: The tenant ID for scoping
            user_id: The user ID for auditing
            db: The database session
            roles: User roles for ACL checks
            request_id: Optional request ID (generated if not provided)
            trace_id: Optional trace ID for distributed tracing
            metadata: Optional additional metadata
        """
        principal = Principal(
            tenant_id=tenant_id,
            user_id=user_id,
            roles=tuple(roles) if isinstance(roles, list) else roles,
        )
        return cls(
            principal=principal,
            db=db,
            request_id=request_id or str(uuid4()),
            trace_id=trace_id,
            metadata=metadata or {},
        )

    def with_principal(self, principal: Principal) -> "RunContext":
        """Create a new RunContext with a different principal."""
        return RunContext(
            principal=principal,
            db=self.db,
            request_id=self.request_id,
            trace_id=self.trace_id,
            now=self.now,
            metadata=self.metadata,
        )

    def with_db(self, db: Any) -> "RunContext":
        """Create a new RunContext with a different database session."""
        return RunContext(
            principal=self.principal,
            db=db,
            request_id=self.request_id,
            trace_id=self.trace_id,
            now=self.now,
            metadata=self.metadata,
        )

    def with_trace_id(self, trace_id: str) -> "RunContext":
        """Create a new RunContext with a different trace ID."""
        return RunContext(
            principal=self.principal,
            db=self.db,
            request_id=self.request_id,
            trace_id=trace_id,
            now=self.now,
            metadata=self.metadata,
        )

    def with_metadata(self, metadata: dict[str, Any]) -> "RunContext":
        """Create a new RunContext with merged metadata."""
        return RunContext(
            principal=self.principal,
            db=self.db,
            request_id=self.request_id,
            trace_id=self.trace_id,
            now=self.now,
            metadata=metadata,
        )
