"""
Audit record models.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorInfo(BaseModel):
    """Error information for failed tool calls."""

    type: str  # Error type/class name
    message: str
    code: str | None = None  # Optional error code
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class AuditRecord(BaseModel):
    """
    Record of a single tool call execution.

    Captures all information needed for auditing and compliance.
    """

    # Unique identifier for this audit record
    id: str

    # Tool identification
    tool_name: str

    # Principal information
    principal_id: str
    tenant_id: str

    # Request tracking
    request_id: str | None = None
    trace_id: str | None = None

    # Timing
    timestamp: datetime
    duration_ms: float | None = None

    # Request details (sanitized - no sensitive data)
    inputs: dict[str, Any] = Field(default_factory=dict)

    # Response data (sanitized)
    outputs: dict[str, Any] | None = None

    # Policy decisions made during execution
    policy_decisions: list[str] = Field(default_factory=list)

    # Result summary
    row_count: int | None = None
    affected_rows: int | None = None

    # Error information (if failed)
    error: ErrorInfo | None = None

    # Optional before/after snapshots for write operations
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any] | None = None

    # Reason for write operations
    reason: str | None = None

    # Additional metadata
    metadata: dict[str, Any] | None = None

    model_config = {"frozen": True}

    def is_success(self) -> bool:
        """Check if the operation was successful."""
        return self.error is None

    def to_log_dict(self) -> dict[str, Any]:
        """Convert to a dict suitable for logging."""
        data = self.model_dump()
        # Convert datetime to ISO string
        data["timestamp"] = self.timestamp.isoformat()
        return data
