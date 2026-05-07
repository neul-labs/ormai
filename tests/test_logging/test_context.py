"""Tests for logging context management."""



from ormai.logging.context import (
    LogContext,
    clear_log_context,
    get_log_context,
    set_log_context,
    update_log_context,
    with_log_context,
)


class TestLogContext:
    def test_defaults(self):
        ctx = LogContext()
        assert ctx.tenant_id is None
        assert ctx.user_id is None
        assert ctx.request_id is None
        assert ctx.trace_id is None
        assert ctx.tool_name is None
        assert ctx.extra == {}

    def test_with_values(self):
        ctx = LogContext(
            tenant_id="acme",
            user_id="user1",
            request_id="req-123",
            trace_id="trace-456",
            tool_name="db.query",
        )
        assert ctx.tenant_id == "acme"
        assert ctx.user_id == "user1"
        assert ctx.request_id == "req-123"
        assert ctx.trace_id == "trace-456"
        assert ctx.tool_name == "db.query"

    def test_with_extra(self):
        ctx = LogContext(extra={"key1": "value1", "key2": 42})
        assert ctx.extra == {"key1": "value1", "key2": 42}

    def test_to_dict_all_fields(self):
        ctx = LogContext(
            tenant_id="acme",
            user_id="user1",
            request_id="req-123",
            trace_id="trace-456",
            tool_name="db.query",
            extra={"custom": "field"},
        )
        d = ctx.to_dict()
        assert d == {
            "tenant_id": "acme",
            "user_id": "user1",
            "request_id": "req-123",
            "trace_id": "trace-456",
            "tool_name": "db.query",
            "custom": "field",
        }

    def test_to_dict_omits_none(self):
        ctx = LogContext(tenant_id="acme", request_id="req-123")
        d = ctx.to_dict()
        assert "tenant_id" in d
        assert "request_id" in d
        assert "user_id" not in d
        assert "trace_id" not in d
        assert "tool_name" not in d

    def test_to_dict_empty(self):
        ctx = LogContext()
        d = ctx.to_dict()
        assert d == {}

    def test_from_run_context(self):
        from ormai.core.context import Principal, RunContext

        run_ctx = RunContext(
            principal=Principal(tenant_id="acme", user_id="user1"),
            db=None,
            request_id="req-123",
            trace_id="trace-456",
        )
        log_ctx = LogContext.from_run_context(run_ctx)
        assert log_ctx.tenant_id == "acme"
        assert log_ctx.user_id == "user1"
        assert log_ctx.request_id == "req-123"
        assert log_ctx.trace_id == "trace-456"


class TestGetLogContext:
    def test_empty_initially(self):
        clear_log_context()
        assert get_log_context() == {}

    def test_returns_copy(self):
        set_log_context({"tenant_id": "acme"})
        ctx = get_log_context()
        ctx["extra_key"] = "extra_value"
        assert "extra_key" not in get_log_context()


class TestSetLogContext:
    def test_set_dict(self):
        set_log_context({"tenant_id": "acme", "user_id": "user1"})
        ctx = get_log_context()
        assert ctx["tenant_id"] == "acme"
        assert ctx["user_id"] == "user1"

    def test_set_log_context_object(self):
        set_log_context(LogContext(tenant_id="acme", request_id="req-123"))
        ctx = get_log_context()
        assert ctx["tenant_id"] == "acme"
        assert ctx["request_id"] == "req-123"

    def test_overwrites_previous(self):
        set_log_context({"tenant_id": "first"})
        set_log_context({"tenant_id": "second"})
        assert get_log_context()["tenant_id"] == "second"


class TestUpdateLogContext:
    def test_adds_fields(self):
        set_log_context({"tenant_id": "acme"})
        update_log_context(tool_name="db.query", user_id="user1")
        ctx = get_log_context()
        assert ctx["tenant_id"] == "acme"
        assert ctx["tool_name"] == "db.query"
        assert ctx["user_id"] == "user1"

    def test_overwrites_existing(self):
        set_log_context({"tenant_id": "acme"})
        update_log_context(tenant_id="new_acme")
        assert get_log_context()["tenant_id"] == "new_acme"

    def test_update_empty_context(self):
        clear_log_context()
        update_log_context(key="value")
        assert get_log_context() == {"key": "value"}


class TestClearLogContext:
    def test_clears_context(self):
        set_log_context({"tenant_id": "acme"})
        clear_log_context()
        assert get_log_context() == {}


class TestWithLogContext:
    def test_sets_and_restores_context(self):
        clear_log_context()
        assert get_log_context() == {}
        with with_log_context(tenant_id="acme"):
            assert get_log_context()["tenant_id"] == "acme"
        assert get_log_context() == {}

    def test_with_log_context_object(self):
        clear_log_context()
        ctx = LogContext(tenant_id="acme", user_id="user1")
        with with_log_context(ctx):
            result = get_log_context()
            assert result["tenant_id"] == "acme"
            assert result["user_id"] == "user1"

    def test_with_dict_context(self):
        clear_log_context()
        with with_log_context({"tenant_id": "acme", "request_id": "req-1"}):
            result = get_log_context()
            assert result["tenant_id"] == "acme"
            assert result["request_id"] == "req-1"

    def test_kwargs_merged_with_existing(self):
        set_log_context({"tenant_id": "acme"})
        with with_log_context(tool_name="db.query"):
            result = get_log_context()
            assert result["tenant_id"] == "acme"
            assert result["tool_name"] == "db.query"
        assert get_log_context() == {"tenant_id": "acme"}

    def test_restores_on_exception(self):
        clear_log_context()
        try:
            with with_log_context(tenant_id="acme"):
                raise RuntimeError("test")
        except RuntimeError:
            pass
        assert get_log_context() == {}

    def test_nested_contexts(self):
        clear_log_context()
        with with_log_context(tenant_id="outer"):
            assert get_log_context()["tenant_id"] == "outer"
            with with_log_context(tenant_id="inner", tool="query"):
                assert get_log_context()["tenant_id"] == "inner"
                assert get_log_context()["tool"] == "query"
            assert get_log_context()["tenant_id"] == "outer"
            assert "tool" not in get_log_context()

    def test_context_parameter_and_kwargs(self):
        clear_log_context()
        ctx = LogContext(tenant_id="acme")
        with with_log_context(ctx, tool_name="db.query"):
            result = get_log_context()
            assert result["tenant_id"] == "acme"
            assert result["tool_name"] == "db.query"

    def test_none_context_with_kwargs(self):
        clear_log_context()
        with with_log_context(None, tenant_id="acme"):
            assert get_log_context()["tenant_id"] == "acme"


class TestContextFilter:
    def test_injects_context_into_record(self):
        import logging

        from ormai.logging.context import ContextFilter

        set_log_context({"tenant_id": "acme", "request_id": "req-1"})
        filt = ContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=None,
            exc_info=None,
        )
        result = filt.filter(record)
        assert result is True
        assert record.tenant_id == "acme"
        assert record.request_id == "req-1"

    def test_does_not_overwrite_existing(self):
        import logging

        from ormai.logging.context import ContextFilter

        set_log_context({"tenant_id": "context_value"})
        filt = ContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=None,
            exc_info=None,
        )
        record.tenant_id = "existing_value"
        filt.filter(record)
        assert record.tenant_id == "existing_value"

    def test_empty_context(self):
        import logging

        from ormai.logging.context import ContextFilter

        clear_log_context()
        filt = ContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=None,
            exc_info=None,
        )
        result = filt.filter(record)
        assert result is True
