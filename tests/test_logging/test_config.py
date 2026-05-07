"""Tests for logging configuration."""

import logging

from ormai.logging.config import (
    LogFormat,
    LogLevel,
    OrmAILogger,
    configure_development_logging,
    configure_logging,
    configure_production_logging,
    get_logger,
)


class TestLogLevel:
    def test_values(self):
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_is_string_enum(self):
        assert isinstance(LogLevel.INFO, str)
        assert LogLevel.INFO == "INFO"


class TestLogFormat:
    def test_values(self):
        assert LogFormat.JSON.value == "json"
        assert LogFormat.TEXT.value == "text"

    def test_is_string_enum(self):
        assert isinstance(LogFormat.JSON, str)
        assert LogFormat.JSON == "json"


class TestOrmAILogger:
    def test_name_property(self):
        logger = OrmAILogger("ormai.test")
        assert logger.name == "ormai.test"

    def test_get_logger_returns_ormai_logger(self):
        logger = get_logger("ormai.tools")
        assert isinstance(logger, OrmAILogger)
        assert logger.name == "ormai.tools"

    def test_debug_logs(self, caplog):
        logger = OrmAILogger("ormai.test.debug")
        with caplog.at_level(logging.DEBUG, logger="ormai.test.debug"):
            logger.debug("debug message", key="value")
        assert "debug message" in caplog.text

    def test_info_logs(self, caplog):
        logger = OrmAILogger("ormai.test.info")
        with caplog.at_level(logging.INFO, logger="ormai.test.info"):
            logger.info("info message", key="value")
        assert "info message" in caplog.text

    def test_warning_logs(self, caplog):
        logger = OrmAILogger("ormai.test.warning")
        with caplog.at_level(logging.WARNING, logger="ormai.test.warning"):
            logger.warning("warning message")
        assert "warning message" in caplog.text

    def test_error_logs(self, caplog):
        logger = OrmAILogger("ormai.test.error")
        with caplog.at_level(logging.ERROR, logger="ormai.test.error"):
            logger.error("error message")
        assert "error message" in caplog.text

    def test_critical_logs(self, caplog):
        logger = OrmAILogger("ormai.test.critical")
        with caplog.at_level(logging.CRITICAL, logger="ormai.test.critical"):
            logger.critical("critical message")
        assert "critical message" in caplog.text

    def test_exception_logs(self, caplog):
        logger = OrmAILogger("ormai.test.exception")
        with caplog.at_level(logging.ERROR, logger="ormai.test.exception"):
            try:
                raise ValueError("test error")
            except ValueError:
                logger.exception("exception occurred")
        assert "exception occurred" in caplog.text

    def test_extra_fields_passed(self, caplog):
        logger = OrmAILogger("ormai.test.extra")
        with caplog.at_level(logging.INFO, logger="ormai.test.extra"):
            logger.info("with extras", tool_name="db.query", duration_ms=15.2)
        record = caplog.records[0]
        assert hasattr(record, "tool_name")
        assert record.tool_name == "db.query"
        assert hasattr(record, "duration_ms")
        assert record.duration_ms == 15.2

    def test_is_enabled_for_with_int(self):
        logger = OrmAILogger("ormai.test.enabled")
        std_logger = logging.getLogger("ormai.test.enabled")
        std_logger.setLevel(logging.WARNING)
        assert not logger.is_enabled_for(logging.DEBUG)
        assert logger.is_enabled_for(logging.WARNING)

    def test_is_enabled_for_with_log_level(self):
        logger = OrmAILogger("ormai.test.enabled")
        std_logger = logging.getLogger("ormai.test.enabled")
        std_logger.setLevel(logging.WARNING)
        assert not logger.is_enabled_for(LogLevel.DEBUG)
        assert logger.is_enabled_for(LogLevel.WARNING)


class TestConfigureLogging:
    def setup_method(self):
        root = logging.getLogger("ormai")
        root.handlers.clear()
        root.setLevel(logging.NOTSET)
        root.propagate = True

    def test_configure_json_format(self):
        configure_logging(level=LogLevel.INFO, format=LogFormat.JSON)
        root = logging.getLogger("ormai")
        assert root.level == logging.INFO
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler.formatter, __import__("ormai.logging.formatters", fromlist=["JSONFormatter"]).JSONFormatter)
        assert not root.propagate

    def test_configure_text_format(self):
        configure_logging(level=LogLevel.DEBUG, format=LogFormat.TEXT)
        root = logging.getLogger("ormai")
        assert root.level == logging.DEBUG
        handler = root.handlers[0]
        assert isinstance(handler.formatter, __import__("ormai.logging.formatters", fromlist=["TextFormatter"]).TextFormatter)

    def test_configure_with_string_level(self):
        configure_logging(level="WARNING", format="json")
        root = logging.getLogger("ormai")
        assert root.level == logging.WARNING

    def test_configure_with_string_format(self):
        configure_logging(level="INFO", format="text")
        root = logging.getLogger("ormai")
        handler = root.handlers[0]
        assert isinstance(handler.formatter, __import__("ormai.logging.formatters", fromlist=["TextFormatter"]).TextFormatter)

    def test_configure_context_filter_added(self):
        from ormai.logging.context import ContextFilter

        configure_logging(include_context=True)
        root = logging.getLogger("ormai")
        handler = root.handlers[0]
        assert any(isinstance(f, ContextFilter) for f in handler.filters)

    def test_configure_context_filter_not_added(self):
        from ormai.logging.context import ContextFilter

        configure_logging(include_context=False)
        root = logging.getLogger("ormai")
        handler = root.handlers[0]
        assert not any(isinstance(f, ContextFilter) for f in handler.filters)

    def test_configure_removes_existing_handlers(self):
        configure_logging(level="INFO", format="json")
        root = logging.getLogger("ormai")
        assert len(root.handlers) == 1
        configure_logging(level="DEBUG", format="json")
        assert len(root.handlers) == 1

    def test_configure_custom_output(self):
        import io

        output = io.StringIO()
        configure_logging(level=LogLevel.INFO, format=LogFormat.TEXT, output=output)
        logger = OrmAILogger("ormai.test.output")
        logger.info("test message")
        content = output.getvalue()
        assert "test message" in content


class TestConfigureProductionLogging:
    def setup_method(self):
        root = logging.getLogger("ormai")
        root.handlers.clear()
        root.setLevel(logging.NOTSET)
        root.propagate = True

    def test_defaults(self):
        configure_production_logging()
        root = logging.getLogger("ormai")
        assert root.level == logging.INFO


class TestConfigureDevelopmentLogging:
    def setup_method(self):
        root = logging.getLogger("ormai")
        root.handlers.clear()
        root.setLevel(logging.NOTSET)
        root.propagate = True

    def test_defaults(self):
        configure_development_logging()
        root = logging.getLogger("ormai")
        assert root.level == logging.DEBUG
