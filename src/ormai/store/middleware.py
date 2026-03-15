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
    ) -> None:
        """
        Initialize the middleware.

        Args:
            store: The audit store to write records to
            sanitize_inputs: Whether to sanitize sensitive data from inputs
        """
        self.store = store
        self.sanitize_inputs = sanitize_inputs

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
                code=e.code,
                message=e.message,
                details=e.details,
            )
            raise

        except Exception as e:
            error_info = ErrorInfo(
                code="INTERNAL_ERROR",
                message=str(e),
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
                code=e.code,
                message=e.message,
                details=e.details,
            )
            raise

        except Exception as e:
            error_info = ErrorInfo(
                code="INTERNAL_ERROR",
                message=str(e),
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

            # Store synchronously
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.store.store(record))
                else:
                    loop.run_until_complete(self.store.store(record))
            except RuntimeError:
                # No event loop, create a new one
                asyncio.run(self.store.store(record))

    def _sanitize(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Sanitize sensitive data from inputs."""
        sensitive_patterns = [
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "auth",
            "credential",
        ]

        result = {}
        for key, value in inputs.items():
            key_lower = key.lower()
            is_sensitive = any(p in key_lower for p in sensitive_patterns)

            if is_sensitive:
                result[key] = "[REDACTED]"
            elif isinstance(value, dict):
                result[key] = self._sanitize(value)
            elif isinstance(value, list):
                result[key] = [
                    self._sanitize(v) if isinstance(v, dict) else v for v in value
                ]
            else:
                result[key] = value

        return result
