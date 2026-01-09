"""
Logging configuration for OrmAI.

Provides easy setup of structured logging for different environments.
"""

from __future__ import annotations

import logging
import sys
from enum import Enum
from typing import Any, TextIO

from ormai.logging.context import ContextFilter
from ormai.logging.formatters import JSONFormatter, TextFormatter


class LogLevel(str, Enum):
    """Log level options."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Log format options."""

    JSON = "json"
    TEXT = "text"


class OrmAILogger:
    """
    OrmAI logger wrapper with context support.

    Provides a convenient interface for logging with automatic context injection.

    Example:
        logger = OrmAILogger("ormai.tools")
        logger.info("Tool called", tool_name="db.query", duration_ms=15.2)
    """

    def __init__(self, name: str) -> None:
        """
        Initialize the logger.

        Args:
            name: Logger name (typically module name)
        """
        self._logger = logging.getLogger(name)

    @property
    def name(self) -> str:
        """Get the logger name."""
        return self._logger.name

    def _log(
        self,
        level: int,
        msg: str,
        *args: Any,
        exc_info: bool | BaseException | None = None,
        **kwargs: Any,
    ) -> None:
        """Internal log method with context field support."""
        # Extract extra fields for the log record
        extra = kwargs.copy()

        self._logger.log(level, msg, *args, exc_info=exc_info, extra=extra)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(
        self,
        msg: str,
        *args: Any,
        exc_info: bool | BaseException | None = None,
        **kwargs: Any,
    ) -> None:
        """Log an error message."""
        self._log(logging.ERROR, msg, *args, exc_info=exc_info, **kwargs)

    def critical(
        self,
        msg: str,
        *args: Any,
        exc_info: bool | BaseException | None = None,
        **kwargs: Any,
    ) -> None:
        """Log a critical message."""
        self._log(logging.CRITICAL, msg, *args, exc_info=exc_info, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an exception message with traceback."""
        self._log(logging.ERROR, msg, *args, exc_info=True, **kwargs)

    def is_enabled_for(self, level: int | LogLevel) -> bool:
        """Check if logger is enabled for the given level."""
        if isinstance(level, LogLevel):
            level = getattr(logging, level.value)
        return self._logger.isEnabledFor(level)


def get_logger(name: str) -> OrmAILogger:
    """
    Get an OrmAI logger by name.

    Args:
        name: Logger name (typically module name, e.g., "ormai.tools")

    Returns:
        An OrmAILogger instance
    """
    return OrmAILogger(name)


def configure_logging(
    level: LogLevel | str = LogLevel.INFO,
    format: LogFormat | str = LogFormat.JSON,
    output: TextIO | None = None,
    include_context: bool = True,
    use_colors: bool = True,
) -> None:
    """
    Configure OrmAI logging.

    Sets up logging with the specified format and level. Should be called
    once at application startup.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Output format (json for production, text for development)
        output: Output stream (defaults to stderr)
        include_context: Whether to include context fields in logs
        use_colors: Whether to use colors in text format (ignored for JSON)

    Example:
        # Production configuration
        configure_logging(level="INFO", format="json")

        # Development configuration
        configure_logging(level="DEBUG", format="text", use_colors=True)
    """
    # Normalize level
    if isinstance(level, str):
        level = LogLevel(level.upper())

    # Normalize format
    if isinstance(format, str):
        format = LogFormat(format.lower())

    # Default output to stderr
    if output is None:
        output = sys.stderr

    # Get the root ormai logger
    root_logger = logging.getLogger("ormai")
    root_logger.setLevel(getattr(logging, level.value))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(output)
    handler.setLevel(getattr(logging, level.value))

    # Set formatter based on format
    if format == LogFormat.JSON:
        formatter = JSONFormatter(include_extra=True)
    else:
        formatter = TextFormatter(use_colors=use_colors)

    handler.setFormatter(formatter)

    # Add context filter if enabled
    if include_context:
        handler.addFilter(ContextFilter())

    root_logger.addHandler(handler)

    # Also configure the root logger to not propagate
    root_logger.propagate = False


def configure_production_logging(level: LogLevel | str = LogLevel.INFO) -> None:
    """
    Configure logging for production environments.

    Sets up JSON logging to stderr with context injection enabled.

    Args:
        level: Log level (default: INFO)
    """
    configure_logging(
        level=level,
        format=LogFormat.JSON,
        include_context=True,
    )


def configure_development_logging(level: LogLevel | str = LogLevel.DEBUG) -> None:
    """
    Configure logging for development environments.

    Sets up colorized text logging to stderr with context injection enabled.

    Args:
        level: Log level (default: DEBUG)
    """
    configure_logging(
        level=level,
        format=LogFormat.TEXT,
        include_context=True,
        use_colors=True,
    )
