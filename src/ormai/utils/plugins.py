"""
Plugin system for ToolsetFactory customization.

Provides hooks for error handling, message transformation, and extensibility.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from ormai.core.errors import OrmAIError


class ErrorContext(BaseModel):
    """Context information about an error occurrence."""

    tool_name: str
    operation: str | None = None
    model: str | None = None
    principal_id: str | None = None
    tenant_id: str | None = None
    request_id: str | None = None


class TransformedError(BaseModel):
    """Error transformed by a plugin."""

    code: str
    message: str
    retry_hints: list[str] = []
    details: dict[str, Any] = {}
    user_message: str | None = None  # Optional user-friendly message
    log_message: str | None = None  # Optional detailed log message


class ErrorPlugin(ABC):
    """
    Base class for error transformation plugins.

    Plugins can transform error messages, add context, and perform side effects.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this plugin."""
        ...

    def transform(
        self,
        error: OrmAIError,
        context: ErrorContext,
    ) -> TransformedError | None:
        """
        Transform an error.

        Return None to use default error handling.
        Return TransformedError to customize the error output.
        """
        return None

    def on_error(self, error: OrmAIError, context: ErrorContext) -> None:
        """
        Hook called when an error occurs.

        Use for side effects like logging, metrics, alerting.
        Does not affect the error returned to the caller.
        """
        pass


class LocalizedErrorPlugin(ErrorPlugin):
    """
    Plugin for internationalized error messages.

    Translates error messages to the user's locale.
    """

    name = "localized_errors"

    # Default English messages
    DEFAULT_MESSAGES: dict[str, str] = {
        "MODEL_NOT_ALLOWED": "You don't have access to this data type: {model}",
        "FIELD_NOT_ALLOWED": "You can't access the field '{field}' on {model}",
        "RELATION_NOT_ALLOWED": "You can't include '{relation}' with {model}",
        "TENANT_SCOPE_REQUIRED": "Please ensure you're logged into the correct account",
        "QUERY_TOO_BROAD": "Please add more filters to narrow down your search",
        "QUERY_BUDGET_EXCEEDED": "This query is too large. Please request fewer results.",
        "WRITE_DISABLED": "You don't have permission to modify this data",
        "WRITE_APPROVAL_REQUIRED": "This change requires approval before it can be saved",
        "MAX_AFFECTED_ROWS_EXCEEDED": "This operation would affect too many records",
        "VALIDATION_ERROR": "Invalid input: {message}",
        "NOT_FOUND": "The requested item was not found",
    }

    def __init__(
        self,
        messages: dict[str, str] | None = None,
        locale: str = "en",
    ) -> None:
        """
        Initialize with custom messages.

        Args:
            messages: Custom messages by error code
            locale: Locale identifier (for future i18n support)
        """
        self.messages = {**self.DEFAULT_MESSAGES, **(messages or {})}
        self.locale = locale

    def transform(
        self,
        error: OrmAIError,
        context: ErrorContext,
    ) -> TransformedError | None:
        """Transform error to user-friendly message."""
        template = self.messages.get(error.code)
        if not template:
            return None

        # Build format context with defaults
        format_ctx = {
            "model": error.details.get("model", "data"),
            "field": error.details.get("field", "field"),
            "relation": error.details.get("relation", "relation"),
            "message": error.message,
        }
        # Add remaining details (but don't override our defaults)
        for key, value in error.details.items():
            if key not in format_ctx:
                format_ctx[key] = value

        # Format the template with error details
        try:
            user_message = template.format(**format_ctx)
        except (KeyError, ValueError):
            user_message = template

        return TransformedError(
            code=error.code,
            message=error.message,
            retry_hints=error.retry_hints,
            details=error.details,
            user_message=user_message,
        )


class VerboseErrorPlugin(ErrorPlugin):
    """
    Plugin for detailed error messages with full context.

    Useful for development and debugging.
    """

    name = "verbose_errors"

    def transform(
        self,
        error: OrmAIError,
        context: ErrorContext,
    ) -> TransformedError:
        """Add full context to error message."""
        log_parts = [
            f"[{error.code}] {error.message}",
            f"Tool: {context.tool_name}",
        ]

        if context.model:
            log_parts.append(f"Model: {context.model}")
        if context.operation:
            log_parts.append(f"Operation: {context.operation}")
        if context.principal_id:
            log_parts.append(f"Principal: {context.principal_id}")
        if context.tenant_id:
            log_parts.append(f"Tenant: {context.tenant_id}")
        if context.request_id:
            log_parts.append(f"Request: {context.request_id}")
        if error.details:
            log_parts.append(f"Details: {error.details}")
        if error.retry_hints:
            log_parts.append(f"Hints: {error.retry_hints}")

        return TransformedError(
            code=error.code,
            message=error.message,
            retry_hints=error.retry_hints,
            details=error.details,
            log_message="\n".join(log_parts),
        )


class TerseErrorPlugin(ErrorPlugin):
    """
    Plugin for minimal error messages.

    Useful for production where you don't want to leak internal details.
    """

    name = "terse_errors"

    # Minimal messages that don't reveal internal structure
    TERSE_MESSAGES: dict[str, str] = {
        "MODEL_NOT_ALLOWED": "Access denied",
        "FIELD_NOT_ALLOWED": "Access denied",
        "RELATION_NOT_ALLOWED": "Access denied",
        "TENANT_SCOPE_REQUIRED": "Authentication required",
        "QUERY_TOO_BROAD": "Query too broad",
        "QUERY_BUDGET_EXCEEDED": "Request too large",
        "WRITE_DISABLED": "Operation not permitted",
        "WRITE_APPROVAL_REQUIRED": "Approval required",
        "MAX_AFFECTED_ROWS_EXCEEDED": "Operation too large",
        "VALIDATION_ERROR": "Invalid input",
        "NOT_FOUND": "Not found",
    }

    def transform(
        self,
        error: OrmAIError,
        context: ErrorContext,
    ) -> TransformedError:
        """Return minimal error without sensitive details."""
        message = self.TERSE_MESSAGES.get(error.code, "An error occurred")

        return TransformedError(
            code=error.code,
            message=message,
            retry_hints=[],  # No hints in terse mode
            details={},  # No details in terse mode
            user_message=message,
        )


class MetricsPlugin(ErrorPlugin):
    """
    Plugin for error metrics collection.

    Tracks error counts and patterns for monitoring.
    """

    name = "metrics"

    def __init__(
        self,
        on_metric: Callable[[str, dict[str, str]], None] | None = None,
    ) -> None:
        """
        Initialize with metrics callback.

        Args:
            on_metric: Callback receiving (metric_name, tags)
        """
        self.on_metric = on_metric
        self._counts: dict[str, int] = {}
        self._by_tool: dict[str, dict[str, int]] = {}
        self._by_model: dict[str, dict[str, int]] = {}

    def on_error(self, error: OrmAIError, context: ErrorContext) -> None:
        """Record error metrics."""
        # Update internal counts
        self._counts[error.code] = self._counts.get(error.code, 0) + 1

        # Track by tool
        if context.tool_name not in self._by_tool:
            self._by_tool[context.tool_name] = {}
        self._by_tool[context.tool_name][error.code] = (
            self._by_tool[context.tool_name].get(error.code, 0) + 1
        )

        # Track by model
        if context.model:
            if context.model not in self._by_model:
                self._by_model[context.model] = {}
            self._by_model[context.model][error.code] = (
                self._by_model[context.model].get(error.code, 0) + 1
            )

        # Call external metrics callback
        if self.on_metric:
            tags = {
                "error_code": error.code,
                "tool": context.tool_name,
            }
            if context.model:
                tags["model"] = context.model
            if context.tenant_id:
                tags["tenant"] = context.tenant_id

            self.on_metric("ormai.error", tags)

    def get_counts(self) -> dict[str, int]:
        """Get error counts by code."""
        return dict(self._counts)

    def get_counts_by_tool(self) -> dict[str, dict[str, int]]:
        """Get error counts by tool."""
        return dict(self._by_tool)

    def get_counts_by_model(self) -> dict[str, dict[str, int]]:
        """Get error counts by model."""
        return dict(self._by_model)

    def reset(self) -> None:
        """Reset all counters."""
        self._counts = {}
        self._by_tool = {}
        self._by_model = {}


class LoggingPlugin(ErrorPlugin):
    """
    Plugin for structured error logging.

    Logs errors in a structured format for log aggregation.
    """

    name = "logging"

    def __init__(
        self,
        logger: Callable[[dict[str, Any]], None] | None = None,
        log_level: str = "error",
    ) -> None:
        """
        Initialize with logger callback.

        Args:
            logger: Callback receiving structured log dict
            log_level: Log level for errors
        """
        self.logger = logger
        self.log_level = log_level

    def on_error(self, error: OrmAIError, context: ErrorContext) -> None:
        """Log error in structured format."""
        if not self.logger:
            return

        log_entry = {
            "level": self.log_level,
            "event": "ormai_error",
            "error_code": error.code,
            "error_message": error.message,
            "tool_name": context.tool_name,
            "operation": context.operation,
            "model": context.model,
            "principal_id": context.principal_id,
            "tenant_id": context.tenant_id,
            "request_id": context.request_id,
            "details": error.details,
        }

        self.logger(log_entry)


class PluginChain:
    """
    Manages a chain of error plugins.

    Plugins are executed in order for transformation,
    and all plugins receive on_error callbacks.
    """

    def __init__(self, plugins: list[ErrorPlugin] | None = None) -> None:
        """Initialize with optional plugins."""
        self.plugins: list[ErrorPlugin] = plugins or []

    def add(self, plugin: ErrorPlugin) -> "PluginChain":
        """Add a plugin to the chain."""
        self.plugins.append(plugin)
        return self

    def remove(self, name: str) -> "PluginChain":
        """Remove a plugin by name."""
        self.plugins = [p for p in self.plugins if p.name != name]
        return self

    def get(self, name: str) -> ErrorPlugin | None:
        """Get a plugin by name."""
        for p in self.plugins:
            if p.name == name:
                return p
        return None

    def process_error(
        self,
        error: OrmAIError,
        context: ErrorContext,
    ) -> TransformedError:
        """
        Process an error through the plugin chain.

        Calls on_error for all plugins, uses first non-None transform result.
        """
        # Call on_error for all plugins (side effects)
        for plugin in self.plugins:
            try:
                plugin.on_error(error, context)
            except Exception:
                pass  # Don't let plugin errors break the chain

        # Find first transformer that returns a result
        for plugin in self.plugins:
            try:
                result = plugin.transform(error, context)
                if result is not None:
                    return result
            except Exception:
                pass

        # Default transformation
        return TransformedError(
            code=error.code,
            message=error.message,
            retry_hints=error.retry_hints,
            details=error.details,
        )
