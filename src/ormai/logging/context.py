"""
Logging context management for OrmAI.

Provides context injection for structured logging, allowing tenant, user,
and request information to be automatically included in log messages.
"""

from __future__ import annotations

import contextvars
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ormai.core.context import RunContext

# Context variable for storing log context
_log_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "ormai_log_context",
    default=None,
)


@dataclass
class LogContext:
    """
    Structured logging context.

    Contains fields that should be included in all log messages within
    a specific scope (e.g., a request or tool call).
    """

    tenant_id: str | None = None
    user_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    tool_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_run_context(cls, ctx: RunContext) -> LogContext:
        """
        Create a LogContext from a RunContext.

        Args:
            ctx: The run context to extract logging fields from

        Returns:
            A LogContext with fields populated from the run context
        """
        return cls(
            tenant_id=ctx.principal.tenant_id,
            user_id=ctx.principal.user_id,
            request_id=ctx.request_id,
            trace_id=ctx.trace_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary of non-None values."""
        result = {}
        if self.tenant_id is not None:
            result["tenant_id"] = self.tenant_id
        if self.user_id is not None:
            result["user_id"] = self.user_id
        if self.request_id is not None:
            result["request_id"] = self.request_id
        if self.trace_id is not None:
            result["trace_id"] = self.trace_id
        if self.tool_name is not None:
            result["tool_name"] = self.tool_name
        result.update(self.extra)
        return result


def get_log_context() -> dict[str, Any]:
    """Get the current log context."""
    ctx = _log_context.get()
    return ctx.copy() if ctx else {}


def set_log_context(context: LogContext | dict[str, Any]) -> None:
    """
    Set the current log context.

    Args:
        context: LogContext or dict of context fields
    """
    if isinstance(context, LogContext):
        _log_context.set(context.to_dict())
    else:
        _log_context.set(context)


def update_log_context(**kwargs: Any) -> None:
    """
    Update the current log context with additional fields.

    Args:
        **kwargs: Fields to add to the context
    """
    current = get_log_context()
    current.update(kwargs)
    _log_context.set(current)


def clear_log_context() -> None:
    """Clear the current log context."""
    _log_context.set(None)


@contextmanager
def with_log_context(
    context: LogContext | dict[str, Any] | None = None,
    **kwargs: Any,
) -> Iterator[None]:
    """
    Context manager for setting log context within a scope.

    Example:
        with with_log_context(tenant_id="acme", request_id="123"):
            logger.info("Processing request")  # Includes tenant_id and request_id

    Args:
        context: Optional LogContext or dict of context fields
        **kwargs: Additional context fields
    """
    # Save current context
    previous = _log_context.get()

    # Build new context
    if context is not None:
        new_context = (
            context.to_dict() if isinstance(context, LogContext) else context.copy()
        )
    else:
        new_context = previous.copy() if previous else {}

    new_context.update(kwargs)
    _log_context.set(new_context)

    try:
        yield
    finally:
        # Restore previous context
        _log_context.set(previous)


class ContextFilter(logging.Filter):
    """
    Logging filter that injects context fields into log records.

    Add this filter to handlers or loggers to automatically include
    context fields in all log messages.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context fields to the log record."""
        context = get_log_context()
        for key, value in context.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True
