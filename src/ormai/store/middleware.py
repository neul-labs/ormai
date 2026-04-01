"""
Audit middleware for automatic tool call logging.
"""

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import uuid4

from ormai.core.context import RunContext
from ormai.core.errors import OrmAIError
from ormai.store.base import AuditStore
from ormai.store.models import AuditRecord, ErrorInfo
from ormai.store.sanitize import sanitize_inputs

T = TypeVar("T")


class AuditMiddleware:
    """
    Middleware that wraps tool executions with audit logging.

    Ensures every tool call produces an audit record, even if it fails.
    """

    def __init__(
        self,
        store: AuditStore,
        sanitize_inputs: bool = True,
        capture_snapshots: bool = False,
    ) -> None:
        """
        Initialize the middleware.

        Args:
            store: The audit store to write records to
            sanitize_inputs: Whether to sanitize sensitive data from inputs
            capture_snapshots: Whether to capture before/after snapshots for mutations
        """
        self.store = store
        self.sanitize_inputs = sanitize_inputs
        self.capture_snapshots = capture_snapshots

    async def wrap_async(
        self,
        tool_name: str,
        ctx: RunContext,
        inputs: dict[str, Any],
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Wrap an async tool execution with audit logging.

        Returns the result of the tool execution.
        Raises any exception from the tool after logging it.
        """
        start_time = time.perf_counter()
        error_info: ErrorInfo | None = None
        row_count: int | None = None
        result: Any = None

        try:
            result = await fn(*args, **kwargs)

            # Try to extract row count from result
            if hasattr(result, "data") and isinstance(result.data, list):
                row_count = len(result.data)

            return result

        except OrmAIError as e:
            error_info = ErrorInfo(
                type=type(e).__name__,
                message=e.message,
                code=e.code,
                details=e.details,
            )
            raise

        except Exception as e:
            error_info = ErrorInfo(
                type=type(e).__name__,
                message=str(e),
                code="INTERNAL_ERROR",
            )
            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            record = AuditRecord(
                id=str(uuid4()),
                tool_name=tool_name,
                principal_id=ctx.principal.user_id,
                tenant_id=ctx.principal.tenant_id,
                request_id=ctx.request_id,
                trace_id=ctx.trace_id,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                inputs=self._sanitize(inputs) if self.sanitize_inputs else inputs,
                row_count=row_count,
                error=error_info,
            )

            await self.store.store(record)

    def wrap_sync(
        self,
        tool_name: str,
        ctx: RunContext,
        inputs: dict[str, Any],
        fn: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Wrap a sync tool execution with audit logging.

        Returns the result of the tool execution.
        Raises any exception from the tool after logging it.
        """
        start_time = time.perf_counter()
        error_info: ErrorInfo | None = None
        row_count: int | None = None
        result: Any = None

        try:
            result = fn(*args, **kwargs)

            # Try to extract row count from result
            if hasattr(result, "data") and isinstance(result.data, list):
                row_count = len(result.data)

            return result

        except OrmAIError as e:
            error_info = ErrorInfo(
                type=type(e).__name__,
                message=e.message,
                code=e.code,
                details=e.details,
            )
            raise

        except Exception as e:
            error_info = ErrorInfo(
                type=type(e).__name__,
                message=str(e),
                code="INTERNAL_ERROR",
            )
            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            record = AuditRecord(
                id=str(uuid4()),
                tool_name=tool_name,
                principal_id=ctx.principal.user_id,
                tenant_id=ctx.principal.tenant_id,
                request_id=ctx.request_id,
                trace_id=ctx.trace_id,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                inputs=self._sanitize(inputs) if self.sanitize_inputs else inputs,
                row_count=row_count,
                error=error_info,
            )

            # Store synchronously using the store's store_sync method
            self.store.store_sync(record)

    async def wrap_mutation_async(
        self,
        tool_name: str,
        ctx: RunContext,
        inputs: dict[str, Any],
        fn: Callable[..., Any],
        before_snapshot: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Wrap an async mutation with audit logging including before/after snapshots.

        Args:
            tool_name: Name of the tool being executed
            ctx: Run context
            inputs: Tool inputs
            fn: The mutation function to execute
            before_snapshot: Optional snapshot of data before mutation
            *args, **kwargs: Arguments to pass to fn

        Returns the result of the mutation.
        """
        start_time = time.perf_counter()
        error_info: ErrorInfo | None = None
        affected_rows: int | None = None
        after_snapshot: dict[str, Any] | None = None
        result: Any = None

        try:
            result = await fn(*args, **kwargs)

            # Extract affected rows and after snapshot from result
            if hasattr(result, "data") and result.data is not None:
                if self.capture_snapshots:
                    after_snapshot = result.data if isinstance(result.data, dict) else None
            if hasattr(result, "updated_count"):
                affected_rows = result.updated_count
            elif hasattr(result, "success") and result.success:
                affected_rows = 1

            return result

        except OrmAIError as e:
            error_info = ErrorInfo(
                type=type(e).__name__,
                message=e.message,
                code=e.code,
                details=e.details,
            )
            raise

        except Exception as e:
            error_info = ErrorInfo(
                type=type(e).__name__,
                message=str(e),
                code="INTERNAL_ERROR",
            )
            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            record = AuditRecord(
                id=str(uuid4()),
                tool_name=tool_name,
                principal_id=ctx.principal.user_id,
                tenant_id=ctx.principal.tenant_id,
                request_id=ctx.request_id,
                trace_id=ctx.trace_id,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                inputs=self._sanitize(inputs) if self.sanitize_inputs else inputs,
                affected_rows=affected_rows,
                error=error_info,
                before_snapshot=before_snapshot if self.capture_snapshots else None,
                after_snapshot=after_snapshot if self.capture_snapshots else None,
            )

            await self.store.store(record)

    def wrap_mutation_sync(
        self,
        tool_name: str,
        ctx: RunContext,
        inputs: dict[str, Any],
        fn: Callable[..., T],
        before_snapshot: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Wrap a sync mutation with audit logging including before/after snapshots.

        Args:
            tool_name: Name of the tool being executed
            ctx: Run context
            inputs: Tool inputs
            fn: The mutation function to execute
            before_snapshot: Optional snapshot of data before mutation
            *args, **kwargs: Arguments to pass to fn

        Returns the result of the mutation.
        """
        start_time = time.perf_counter()
        error_info: ErrorInfo | None = None
        affected_rows: int | None = None
        after_snapshot: dict[str, Any] | None = None
        result: Any = None

        try:
            result = fn(*args, **kwargs)

            # Extract affected rows and after snapshot from result
            if hasattr(result, "data") and result.data is not None:
                if self.capture_snapshots:
                    after_snapshot = result.data if isinstance(result.data, dict) else None
            if hasattr(result, "updated_count"):
                affected_rows = result.updated_count
            elif hasattr(result, "success") and result.success:
                affected_rows = 1

            return result

        except OrmAIError as e:
            error_info = ErrorInfo(
                type=type(e).__name__,
                message=e.message,
                code=e.code,
                details=e.details,
            )
            raise

        except Exception as e:
            error_info = ErrorInfo(
                type=type(e).__name__,
                message=str(e),
                code="INTERNAL_ERROR",
            )
            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            record = AuditRecord(
                id=str(uuid4()),
                tool_name=tool_name,
                principal_id=ctx.principal.user_id,
                tenant_id=ctx.principal.tenant_id,
                request_id=ctx.request_id,
                trace_id=ctx.trace_id,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                inputs=self._sanitize(inputs) if self.sanitize_inputs else inputs,
                affected_rows=affected_rows,
                error=error_info,
                before_snapshot=before_snapshot if self.capture_snapshots else None,
                after_snapshot=after_snapshot if self.capture_snapshots else None,
            )

            # Store synchronously using the store's store_sync method
            self.store.store_sync(record)

    def _sanitize(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Sanitize sensitive data from inputs using regex pattern matching."""
        return sanitize_inputs(inputs)
