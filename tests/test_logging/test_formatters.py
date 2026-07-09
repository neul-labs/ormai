"""Tests for log formatters."""

import json
import logging

import pytest

from ormai.logging.formatters import JSONFormatter, TextFormatter


def _make_record(
    msg="test message",
    name="ormai.test",
    level=logging.INFO,
    **extra,
):
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="test.py",
        lineno=1,
        msg=msg,
        args=None,
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


class TestJSONFormatter:
    def test_basic_format(self):
        formatter = JSONFormatter()
        record = _make_record()
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "ormai.test"
        assert "timestamp" in data

    def test_context_fields(self):
        formatter = JSONFormatter()
        record = _make_record(tenant_id="acme", user_id="user1", request_id="req-1")
        output = formatter.format(record)
        data = json.loads(output)
        assert data["tenant_id"] == "acme"
        assert data["user_id"] == "user1"
        assert data["request_id"] == "req-1"

    def test_trace_and_tool(self):
        formatter = JSONFormatter()
        record = _make_record(trace_id="trace-1", tool_name="db.query")
        output = formatter.format(record)
        data = json.loads(output)
        assert data["trace_id"] == "trace-1"
        assert data["tool_name"] == "db.query"

    def test_duration_ms(self):
        formatter = JSONFormatter()
        record = _make_record(duration_ms=42.5)
        output = formatter.format(record)
        data = json.loads(output)
        assert data["duration_ms"] == 42.5

    def test_missing_context_fields_omitted(self):
        formatter = JSONFormatter()
        record = _make_record()
        output = formatter.format(record)
        data = json.loads(output)
        assert "tenant_id" not in data
        assert "user_id" not in data
        assert "request_id" not in data
        assert "trace_id" not in data
        assert "tool_name" not in data
        assert "duration_ms" not in data

    def test_extra_fields_included(self):
        formatter = JSONFormatter(include_extra=True)
        record = _make_record(custom_key="custom_value")
        output = formatter.format(record)
        data = json.loads(output)
        assert "extra" in data
        assert data["extra"]["custom_key"] == "custom_value"

    def test_extra_fields_excluded_when_disabled(self):
        formatter = JSONFormatter(include_extra=False)
        record = _make_record(custom_key="custom_value")
        output = formatter.format(record)
        data = json.loads(output)
        assert "extra" not in data

    def test_non_serializable_extra_converted_to_string(self):
        formatter = JSONFormatter(include_extra=True)
        record = _make_record(non_serializable=set([1, 2, 3]))
        output = formatter.format(record)
        data = json.loads(output)
        assert "extra" in data
        assert isinstance(data["extra"]["non_serializable"], str)

    def test_exception_info(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="ormai.test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="error occurred",
            args=None,
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert data["exception"]["message"] == "test error"

    def test_valid_json_output(self):
        formatter = JSONFormatter()
        record = _make_record(
            tenant_id="acme",
            user_id="user1",
            duration_ms=10.5,
            custom="value",
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_ensure_ascii_false(self):
        formatter = JSONFormatter()
        record = _make_record(msg="mensagem com açentos")
        output = formatter.format(record)
        assert "açentos" in output


class TestTextFormatter:
    def test_basic_format(self):
        formatter = TextFormatter(use_colors=False)
        record = _make_record()
        output = formatter.format(record)
        assert "test message" in output
        assert "INFO" in output
        assert "ormai.test" in output

    def test_timestamp_format(self):
        formatter = TextFormatter(use_colors=False)
        record = _make_record()
        output = formatter.format(record)
        import re

        assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", output)

    def test_context_fields(self):
        formatter = TextFormatter(use_colors=False)
        record = _make_record(tenant_id="acme", request_id="req-1", tool_name="db.query")
        output = formatter.format(record)
        assert "tenant_id=acme" in output
        assert "request_id=req-1" in output
        assert "tool_name=db.query" in output

    def test_context_brackets(self):
        formatter = TextFormatter(use_colors=False)
        record = _make_record(tenant_id="acme")
        output = formatter.format(record)
        assert "[tenant_id=acme]" in output

    def test_no_context_when_empty(self):
        formatter = TextFormatter(use_colors=False)
        record = _make_record()
        output = formatter.format(record)
        assert "[" not in output or "[]" not in output

    def test_duration_ms(self):
        formatter = TextFormatter(use_colors=False)
        record = _make_record(duration_ms=15.3)
        output = formatter.format(record)
        assert "15.3ms" in output

    def test_no_duration_when_absent(self):
        formatter = TextFormatter(use_colors=False)
        record = _make_record()
        output = formatter.format(record)
        assert "ms)" not in output

    def test_colors_enabled(self):
        formatter = TextFormatter(use_colors=True)
        record = _make_record(level=logging.INFO)
        output = formatter.format(record)
        assert "\033[32m" in output

    def test_colors_disabled(self):
        formatter = TextFormatter(use_colors=False)
        record = _make_record(level=logging.INFO)
        output = formatter.format(record)
        assert "\033[" not in output

    def test_warning_color(self):
        formatter = TextFormatter(use_colors=True)
        record = _make_record(level=logging.WARNING)
        output = formatter.format(record)
        assert "\033[33m" in output

    def test_error_color(self):
        formatter = TextFormatter(use_colors=True)
        record = _make_record(level=logging.ERROR)
        output = formatter.format(record)
        assert "\033[31m" in output

    def test_debug_color(self):
        formatter = TextFormatter(use_colors=True)
        record = _make_record(level=logging.DEBUG)
        output = formatter.format(record)
        assert "\033[36m" in output

    def test_critical_color(self):
        formatter = TextFormatter(use_colors=True)
        record = _make_record(level=logging.CRITICAL)
        output = formatter.format(record)
        assert "\033[35m" in output

    def test_exception_info(self):
        formatter = TextFormatter(use_colors=False)
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="ormai.test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="error occurred",
            args=None,
            exc_info=exc_info,
        )
        output = formatter.format(record)
        assert "ValueError" in output
        assert "test error" in output

    def test_level_padding(self):
        formatter = TextFormatter(use_colors=False)
        record = _make_record(level=logging.INFO)
        output = formatter.format(record)
        assert "INFO    " in output