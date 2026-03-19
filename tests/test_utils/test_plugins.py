"""Tests for the plugin system."""

import pytest

from ormai.core.errors import (
    FieldNotAllowedError,
    ModelNotAllowedError,
    NotFoundError,
    OrmAIError,
    QueryBudgetExceededError,
)
from ormai.utils.plugins import (
    ErrorContext,
    ErrorPlugin,
    LocalizedErrorPlugin,
    LoggingPlugin,
    MetricsPlugin,
    PluginChain,
    TerseErrorPlugin,
    TransformedError,
    VerboseErrorPlugin,
)


class TestErrorContext:
    """Tests for ErrorContext."""

    def test_basic_context(self):
        """Test creating error context."""
        ctx = ErrorContext(
            tool_name="db.query",
            operation="query",
            model="Customer",
            principal_id="user-1",
            tenant_id="tenant-1",
            request_id="req-123",
        )

        assert ctx.tool_name == "db.query"
        assert ctx.model == "Customer"
        assert ctx.tenant_id == "tenant-1"

    def test_minimal_context(self):
        """Test context with only required fields."""
        ctx = ErrorContext(tool_name="db.query")

        assert ctx.tool_name == "db.query"
        assert ctx.operation is None
        assert ctx.model is None


class TestTransformedError:
    """Tests for TransformedError."""

    def test_basic_transformed_error(self):
        """Test creating transformed error."""
        error = TransformedError(
            code="TEST_ERROR",
            message="Test error message",
            retry_hints=["Try again"],
            details={"key": "value"},
            user_message="Something went wrong",
            log_message="Detailed log info",
        )

        assert error.code == "TEST_ERROR"
        assert error.message == "Test error message"
        assert error.user_message == "Something went wrong"
        assert error.log_message == "Detailed log info"

    def test_default_values(self):
        """Test default values."""
        error = TransformedError(code="TEST", message="msg")

        assert error.retry_hints == []
        assert error.details == {}
        assert error.user_message is None


class TestLocalizedErrorPlugin:
    """Tests for LocalizedErrorPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create a localized error plugin."""
        return LocalizedErrorPlugin()

    @pytest.fixture
    def context(self):
        """Create error context."""
        return ErrorContext(tool_name="db.query", model="Customer")

    def test_model_not_allowed(self, plugin, context):
        """Test translation of model not allowed error."""
        error = ModelNotAllowedError("Customer", allowed_models=["Order"])

        result = plugin.transform(error, context)

        assert result is not None
        assert "don't have access" in result.user_message

    def test_field_not_allowed(self, plugin, context):
        """Test translation of field not allowed error."""
        error = FieldNotAllowedError("ssn", "Customer")

        result = plugin.transform(error, context)

        assert result is not None
        assert "ssn" in result.user_message
        assert "Customer" in result.user_message

    def test_query_budget_exceeded(self, plugin, context):
        """Test translation of budget exceeded error."""
        error = QueryBudgetExceededError("max_rows", 100, 500)

        result = plugin.transform(error, context)

        assert result is not None
        assert "too large" in result.user_message.lower()

    def test_custom_messages(self, context):
        """Test custom message templates."""
        plugin = LocalizedErrorPlugin(
            messages={"MODEL_NOT_ALLOWED": "Cannot access {model}"}
        )

        error = ModelNotAllowedError("Customer")

        result = plugin.transform(error, context)

        assert result.user_message == "Cannot access Customer"

    def test_unknown_error_returns_none(self, plugin, context):
        """Test that unknown errors return None."""

        class CustomError(OrmAIError):
            code = "CUSTOM_UNKNOWN"

        error = CustomError("Custom message")

        result = plugin.transform(error, context)

        assert result is None


class TestVerboseErrorPlugin:
    """Tests for VerboseErrorPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create verbose error plugin."""
        return VerboseErrorPlugin()

    def test_includes_all_context(self, plugin):
        """Test that verbose output includes all context."""
        context = ErrorContext(
            tool_name="db.query",
            operation="query",
            model="Customer",
            principal_id="user-1",
            tenant_id="tenant-1",
            request_id="req-123",
        )

        error = ModelNotAllowedError("Customer")

        result = plugin.transform(error, context)

        assert result is not None
        assert "MODEL_NOT_ALLOWED" in result.log_message
        assert "db.query" in result.log_message
        assert "Customer" in result.log_message
        assert "user-1" in result.log_message
        assert "tenant-1" in result.log_message
        assert "req-123" in result.log_message

    def test_includes_hints(self, plugin):
        """Test that retry hints are included."""
        context = ErrorContext(tool_name="db.query")
        error = ModelNotAllowedError("Customer", allowed_models=["Order", "Product"])

        result = plugin.transform(error, context)

        assert "Hints:" in result.log_message


class TestTerseErrorPlugin:
    """Tests for TerseErrorPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create terse error plugin."""
        return TerseErrorPlugin()

    @pytest.fixture
    def context(self):
        """Create error context."""
        return ErrorContext(tool_name="db.query", model="Customer")

    def test_hides_model_name(self, plugin, context):
        """Test that model name is hidden."""
        error = ModelNotAllowedError("SensitiveTable")

        result = plugin.transform(error, context)

        assert result is not None
        assert "SensitiveTable" not in result.message
        assert "SensitiveTable" not in result.user_message
        assert result.details == {}

    def test_no_hints(self, plugin, context):
        """Test that hints are not included."""
        error = FieldNotAllowedError("password", "User", allowed_fields=["id", "name"])

        result = plugin.transform(error, context)

        assert result.retry_hints == []

    def test_generic_messages(self, plugin, context):
        """Test that messages are generic."""
        error = NotFoundError("Customer", 123)

        result = plugin.transform(error, context)

        assert result.message == "Not found"
        assert "123" not in result.message


class TestMetricsPlugin:
    """Tests for MetricsPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create metrics plugin."""
        return MetricsPlugin()

    @pytest.fixture
    def context(self):
        """Create error context."""
        return ErrorContext(
            tool_name="db.query",
            model="Customer",
            tenant_id="tenant-1",
        )

    def test_counts_errors(self, plugin, context):
        """Test error counting."""
        error1 = ModelNotAllowedError("Customer")
        error2 = ModelNotAllowedError("Order")
        error3 = FieldNotAllowedError("password", "User")

        plugin.on_error(error1, context)
        plugin.on_error(error2, context)
        plugin.on_error(error3, context)

        counts = plugin.get_counts()

        assert counts["MODEL_NOT_ALLOWED"] == 2
        assert counts["FIELD_NOT_ALLOWED"] == 1

    def test_counts_by_tool(self, plugin):
        """Test error counting by tool."""
        error = ModelNotAllowedError("Customer")

        ctx1 = ErrorContext(tool_name="db.query")
        ctx2 = ErrorContext(tool_name="db.get")

        plugin.on_error(error, ctx1)
        plugin.on_error(error, ctx1)
        plugin.on_error(error, ctx2)

        by_tool = plugin.get_counts_by_tool()

        assert by_tool["db.query"]["MODEL_NOT_ALLOWED"] == 2
        assert by_tool["db.get"]["MODEL_NOT_ALLOWED"] == 1

    def test_counts_by_model(self, plugin):
        """Test error counting by model."""
        error = FieldNotAllowedError("password", "User")

        ctx1 = ErrorContext(tool_name="db.query", model="Customer")
        ctx2 = ErrorContext(tool_name="db.query", model="Order")

        plugin.on_error(error, ctx1)
        plugin.on_error(error, ctx1)
        plugin.on_error(error, ctx2)

        by_model = plugin.get_counts_by_model()

        assert by_model["Customer"]["FIELD_NOT_ALLOWED"] == 2
        assert by_model["Order"]["FIELD_NOT_ALLOWED"] == 1

    def test_callback(self, context):
        """Test metrics callback."""
        received_metrics = []

        def on_metric(name, tags):
            received_metrics.append((name, tags))

        plugin = MetricsPlugin(on_metric=on_metric)
        error = ModelNotAllowedError("Customer")

        plugin.on_error(error, context)

        assert len(received_metrics) == 1
        name, tags = received_metrics[0]
        assert name == "ormai.error"
        assert tags["error_code"] == "MODEL_NOT_ALLOWED"
        assert tags["tool"] == "db.query"
        assert tags["model"] == "Customer"

    def test_reset(self, plugin, context):
        """Test resetting counters."""
        error = ModelNotAllowedError("Customer")
        plugin.on_error(error, context)

        assert plugin.get_counts()["MODEL_NOT_ALLOWED"] == 1

        plugin.reset()

        assert plugin.get_counts() == {}


class TestLoggingPlugin:
    """Tests for LoggingPlugin."""

    def test_logs_structured_data(self):
        """Test structured logging."""
        logs = []

        def logger(entry):
            logs.append(entry)

        plugin = LoggingPlugin(logger=logger)

        context = ErrorContext(
            tool_name="db.query",
            operation="query",
            model="Customer",
            principal_id="user-1",
            tenant_id="tenant-1",
            request_id="req-123",
        )

        error = ModelNotAllowedError("Customer")

        plugin.on_error(error, context)

        assert len(logs) == 1
        log = logs[0]
        assert log["level"] == "error"
        assert log["event"] == "ormai_error"
        assert log["error_code"] == "MODEL_NOT_ALLOWED"
        assert log["tool_name"] == "db.query"
        assert log["model"] == "Customer"

    def test_no_logger(self):
        """Test that no logger is safe."""
        plugin = LoggingPlugin()  # No logger callback
        context = ErrorContext(tool_name="db.query")
        error = ModelNotAllowedError("Customer")

        # Should not raise
        plugin.on_error(error, context)


class TestPluginChain:
    """Tests for PluginChain."""

    def test_add_and_get_plugin(self):
        """Test adding and getting plugins."""
        chain = PluginChain()
        plugin = MetricsPlugin()

        chain.add(plugin)

        assert chain.get("metrics") is plugin

    def test_remove_plugin(self):
        """Test removing a plugin."""
        chain = PluginChain([MetricsPlugin(), LocalizedErrorPlugin()])

        chain.remove("metrics")

        assert chain.get("metrics") is None
        assert chain.get("localized_errors") is not None

    def test_first_transformer_wins(self):
        """Test that first transformer result is used."""
        chain = PluginChain([
            TerseErrorPlugin(),
            VerboseErrorPlugin(),
        ])

        context = ErrorContext(tool_name="db.query")
        error = ModelNotAllowedError("Customer")

        result = chain.process_error(error, context)

        # Terse is first, so its message should be used
        assert result.message == "Access denied"

    def test_all_on_error_called(self):
        """Test that all plugins receive on_error."""
        metrics1 = MetricsPlugin()
        metrics2 = MetricsPlugin()

        chain = PluginChain([metrics1, metrics2])

        context = ErrorContext(tool_name="db.query")
        error = ModelNotAllowedError("Customer")

        chain.process_error(error, context)

        # Both should have recorded the error
        assert metrics1.get_counts()["MODEL_NOT_ALLOWED"] == 1
        assert metrics2.get_counts()["MODEL_NOT_ALLOWED"] == 1

    def test_default_transformation(self):
        """Test default transformation when no plugin transforms."""

        class NoOpPlugin(ErrorPlugin):
            name = "noop"

        chain = PluginChain([NoOpPlugin()])

        context = ErrorContext(tool_name="db.query")
        error = ModelNotAllowedError("Customer")

        result = chain.process_error(error, context)

        # Should use original error values
        assert result.code == "MODEL_NOT_ALLOWED"
        assert "Customer" in result.message

    def test_plugin_error_doesnt_break_chain(self):
        """Test that plugin errors don't break the chain."""

        class BrokenPlugin(ErrorPlugin):
            name = "broken"

            def transform(self, error, context):
                raise RuntimeError("Plugin error!")

            def on_error(self, error, context):
                raise RuntimeError("Plugin error!")

        metrics = MetricsPlugin()
        chain = PluginChain([BrokenPlugin(), metrics, LocalizedErrorPlugin()])

        context = ErrorContext(tool_name="db.query")
        error = ModelNotAllowedError("Customer")

        # Should not raise, and should still work
        result = chain.process_error(error, context)

        assert result is not None
        # Metrics should still have recorded
        assert metrics.get_counts()["MODEL_NOT_ALLOWED"] == 1

    def test_fluent_api(self):
        """Test fluent API for building chains."""
        chain = (
            PluginChain()
            .add(MetricsPlugin())
            .add(LocalizedErrorPlugin())
            .remove("metrics")
        )

        assert chain.get("metrics") is None
        assert chain.get("localized_errors") is not None
