"""
Log formatters for OrmAI.

Provides JSON and text formatters for different deployment environments.
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    JSON-structured log formatter for production use.

    Outputs logs as single-line JSON objects, compatible with log aggregation
    systems like CloudWatch, Datadog, ELK, etc.

    Fields included:
    - timestamp: ISO 8601 UTC timestamp
    - level: Log level name
    - logger: Logger name
    - message: Log message
    - tenant_id: Tenant ID (if available in record)
    - user_id: User ID (if available in record)
    - request_id: Request ID (if available in record)
    - trace_id: Trace ID (if available in record)
    - tool_name: Tool name (if available in record)
    - duration_ms: Duration in milliseconds (if available in record)
    - exception: Exception info (if present)
    - extra: Any additional fields
    """

    # Fields that are part of the standard schema
    STANDARD_FIELDS = {
        "timestamp",
        "level",
        "logger",
        "message",
        "tenant_id",
        "user_id",
        "request_id",
        "trace_id",
        "tool_name",
        "duration_ms",
        "exception",
    }

    # Fields to exclude from extra
    EXCLUDE_FIELDS = {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "message",
        "taskName",
    }

    def __init__(self, include_extra: bool = True) -> None:
        """
        Initialize the JSON formatter.

        Args:
            include_extra: Whether to include extra fields from the log record
        """
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        log_dict: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context fields if present
        for field in ["tenant_id", "user_id", "request_id", "trace_id", "tool_name"]:
            value = getattr(record, field, None)
            if value is not None:
                log_dict[field] = value

        # Add duration if present
        duration = getattr(record, "duration_ms", None)
        if duration is not None:
            log_dict["duration_ms"] = duration

        # Add exception info if present
        if record.exc_info:
            log_dict["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields
        if self.include_extra:
            extra = {}
            for key, value in record.__dict__.items():
                # Skip excluded fields, standard fields, and private attributes
                if (
                    key not in self.EXCLUDE_FIELDS
                    and key not in self.STANDARD_FIELDS
                    and not key.startswith("_")
                ):
                    try:
                        # Ensure value is JSON serializable
                        json.dumps(value)
                        extra[key] = value
                    except (TypeError, ValueError):
                        extra[key] = str(value)
            if extra:
                log_dict["extra"] = extra

        return json.dumps(log_dict, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """
    Human-readable text formatter for development use.

    Outputs logs in a colorized, easy-to-read format suitable for local
    development and debugging.
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True) -> None:
        """
        Initialize the text formatter.

        Args:
            use_colors: Whether to use ANSI colors in output
        """
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as readable text."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Build level string with optional color
        level = record.levelname
        if self.use_colors and level in self.COLORS:
            level = f"{self.COLORS[level]}{level:8}{self.RESET}"
        else:
            level = f"{level:8}"

        # Build message
        message = record.getMessage()

        # Build context string
        context_parts = []
        for field in ["tenant_id", "request_id", "tool_name"]:
            value = getattr(record, field, None)
            if value is not None:
                context_parts.append(f"{field}={value}")
        context = f" [{', '.join(context_parts)}]" if context_parts else ""

        # Build duration string
        duration = getattr(record, "duration_ms", None)
        duration_str = f" ({duration:.1f}ms)" if duration is not None else ""

        # Format base log line
        log_line = f"{timestamp} {level} {record.name}{context}: {message}{duration_str}"

        # Add exception if present
        if record.exc_info:
            log_line += "\n" + self.formatException(record.exc_info)

        return log_line
