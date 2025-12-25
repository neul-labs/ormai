"""
Tool call recorder for capturing and storing execution traces.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ormai.core.context import RunContext


@dataclass
class RecordedCall:
    """
    A recorded tool call.

    Captures all information needed to replay and verify a tool execution.
    """

    # Unique identifier
    id: str = field(default_factory=lambda: str(uuid4()))

    # Tool information
    tool_name: str = ""

    # Context snapshot
    principal_id: str = ""
    tenant_id: str = ""
    roles: list[str] = field(default_factory=list)

    # Request data
    inputs: dict[str, Any] = field(default_factory=dict)

    # Response data
    outputs: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    # Timing
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0

    # Policy decisions
    policy_decisions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "roles": self.roles,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "policy_decisions": self.policy_decisions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecordedCall":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid4())),
            tool_name=data.get("tool_name", ""),
            principal_id=data.get("principal_id", ""),
            tenant_id=data.get("tenant_id", ""),
            roles=data.get("roles", []),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs"),
            error=data.get("error"),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(timezone.utc),
            duration_ms=data.get("duration_ms", 0.0),
            policy_decisions=data.get("policy_decisions", []),
        )

    def is_success(self) -> bool:
        """Check if the call was successful."""
        return self.error is None


class CallRecorder:
    """
    Records tool calls for later replay and analysis.

    Usage:
        recorder = CallRecorder()

        # Record calls during execution
        with recorder.record_call("db.query", ctx, inputs) as call:
            result = await tool.execute(...)
            call.outputs = result.model_dump()

        # Save recordings
        recorder.save("recordings.jsonl")
    """

    def __init__(self) -> None:
        self._calls: list[RecordedCall] = []

    def record_call(
        self,
        tool_name: str,
        ctx: RunContext,
        inputs: dict[str, Any],
    ) -> "CallContext":
        """
        Start recording a tool call.

        Returns a context manager that captures the call result.
        """
        call = RecordedCall(
            tool_name=tool_name,
            principal_id=ctx.principal.user_id,
            tenant_id=ctx.principal.tenant_id,
            roles=list(ctx.principal.roles),
            inputs=inputs,
        )
        return CallContext(call, self)

    def add_call(self, call: RecordedCall) -> None:
        """Add a completed call to the recordings."""
        self._calls.append(call)

    @property
    def calls(self) -> list[RecordedCall]:
        """Get all recorded calls."""
        return list(self._calls)

    def clear(self) -> None:
        """Clear all recordings."""
        self._calls.clear()

    def save(self, path: Path | str) -> None:
        """
        Save recordings to a JSONL file.

        Each line is a JSON-encoded call record.
        """
        path = Path(path)
        with path.open("w") as f:
            for call in self._calls:
                f.write(json.dumps(call.to_dict()) + "\n")

    def load(self, path: Path | str) -> None:
        """
        Load recordings from a JSONL file.

        Appends to existing recordings.
        """
        path = Path(path)
        with path.open("r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    self._calls.append(RecordedCall.from_dict(data))

    @classmethod
    def from_file(cls, path: Path | str) -> "CallRecorder":
        """Create a recorder and load recordings from file."""
        recorder = cls()
        recorder.load(path)
        return recorder

    def filter_by_tool(self, tool_name: str) -> list[RecordedCall]:
        """Get calls for a specific tool."""
        return [c for c in self._calls if c.tool_name == tool_name]

    def filter_by_tenant(self, tenant_id: str) -> list[RecordedCall]:
        """Get calls for a specific tenant."""
        return [c for c in self._calls if c.tenant_id == tenant_id]

    def filter_errors(self) -> list[RecordedCall]:
        """Get only failed calls."""
        return [c for c in self._calls if c.error is not None]

    def filter_success(self) -> list[RecordedCall]:
        """Get only successful calls."""
        return [c for c in self._calls if c.error is None]


class CallContext:
    """Context manager for recording a single call."""

    def __init__(self, call: RecordedCall, recorder: CallRecorder) -> None:
        self._call = call
        self._recorder = recorder
        self._start_time: float = 0.0

    def __enter__(self) -> RecordedCall:
        import time
        self._start_time = time.perf_counter()
        return self._call

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        import time
        self._call.duration_ms = (time.perf_counter() - self._start_time) * 1000

        if exc_val is not None:
            self._call.error = {
                "type": exc_type.__name__ if exc_type else "Unknown",
                "message": str(exc_val),
            }

        self._recorder.add_call(self._call)
