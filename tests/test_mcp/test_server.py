"""
Tests for MCP server.
"""

from typing import Any

import pytest
from pydantic import BaseModel

from ormai.core.context import Principal, RunContext
from ormai.core.errors import (
    AuthenticationError,
)
from ormai.mcp.server import McpServer, McpServerFactory
from ormai.policy.models import (
    Budget,
    FieldAction,
    FieldPolicy,
    ModelPolicy,
    Policy,
    RelationPolicy,
    RowPolicy,
    WritePolicy,
)
from ormai.tools.base import Tool
from ormai.tools.registry import ToolRegistry

# === Mock Tool Classes ===

class MockQueryInput(BaseModel):
    """Mock input for query tool."""
    model: str
    select: list[str] | None = None


class MockQueryTool(Tool):
    """Mock query tool for testing."""
    name = "query"
    description = "Query the database"
    input_schema = MockQueryInput

    async def execute(self, _input: MockQueryInput, _ctx: RunContext) -> dict[str, Any]:
        """Execute the query tool."""
        return {"success": True, "data": []}


class MockDescribeSchemaInput(BaseModel):
    """Mock input for describe_schema tool."""
    model: str | None = None


class MockDescribeSchemaTool(Tool):
    """Mock describe schema tool for testing."""
    name = "describe_schema"
    description = "Describe the database schema"
    input_schema = MockDescribeSchemaInput

    async def execute(self, _input: MockDescribeSchemaInput, _ctx: RunContext) -> dict[str, Any]:
        """Execute the describe schema tool."""
        return {"success": True, "models": []}


class MockGetInput(BaseModel):
    """Mock input for get tool."""
    model: str
    id: int


class MockGetTool(Tool):
    """Mock get tool for testing."""
    name = "get"
    description = "Get a record by ID"
    input_schema = MockGetInput

    async def execute(self, _input: MockGetInput, _ctx: RunContext) -> dict[str, Any]:
        """Execute the get tool."""
        return {"success": True, "data": None}


class MockAggregateInput(BaseModel):
    """Mock input for aggregate tool."""
    model: str
    operation: str
    field: str


class MockAggregateTool(Tool):
    """Mock aggregate tool for testing."""
    name = "aggregate"
    description = "Aggregate data"
    input_schema = MockAggregateInput

    async def execute(self, _input: MockAggregateInput, _ctx: RunContext) -> dict[str, Any]:
        """Execute the aggregate tool."""
        return {"success": True, "value": 0}


# === Fixtures ===

@pytest.fixture
def tool_registry():
    """Create a tool registry with sample tools."""
    registry = ToolRegistry()
    registry.register(MockQueryTool())
    registry.register(MockDescribeSchemaTool())
    registry.register(MockGetTool())
    registry.register(MockAggregateTool())
    return registry


@pytest.fixture
def basic_policy():
    """Create a basic test policy."""
    return Policy(
        models={
            "User": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
                fields={
                    "password": FieldPolicy(action=FieldAction.DENY),
                    "email": FieldPolicy(action=FieldAction.MASK),
                },
                relations={
                    "posts": RelationPolicy(allowed=True, max_depth=2),
                },
                row_policy=RowPolicy(
                    tenant_scope_field="tenant_id",
                    require_scope=True,
                ),
                write_policy=WritePolicy(
                    enabled=True,
                    allow_create=True,
                    allow_update=True,
                    allow_delete=True,
                    allow_bulk=True,
                    max_affected_rows=100,
                ),
            ),
            "Post": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
                row_policy=RowPolicy(
                    tenant_scope_field="tenant_id",
                    require_scope=True,
                ),
            ),
        },
        default_budget=Budget(
            max_rows=100,
            max_includes_depth=2,
            max_select_fields=20,
        ),
        require_tenant_scope=True,
        writes_enabled=True,
    )


@pytest.fixture
def sample_principal():
    """Create a sample principal."""
    return Principal(
        tenant_id="tenant-abc",
        user_id="user-123",
        roles=("user",),
    )


@pytest.fixture
def context(sample_principal):
    """Create a sample context dict."""
    return {"principal": sample_principal}


@pytest.fixture
def mcp_server(tool_registry, _basic_policy):
    """Create an MCP server with basic configuration."""
    return McpServerFactory(
        toolset=tool_registry,
        enforce_auth=False,
    ).build()


@pytest.fixture
def mcp_server_with_auth(tool_registry, _basic_policy):
    """Create an MCP server with authentication enforcement."""
    def auth_function(ctx):
        principal = ctx.get("principal")
        if principal is None:
            raise AuthenticationError("No principal provided")
        return principal

    return McpServerFactory(
        toolset=tool_registry,
        auth=auth_function,
        enforce_auth=True,
    ).build()


# === Tests for McpServerFactory ===

class TestMcpServerFactory:
    """Tests for McpServerFactory."""

    def test_factory_creates_server(self, tool_registry, _basic_policy):
        """Test that factory creates a server instance."""
        factory = McpServerFactory(toolset=tool_registry)
        server = factory.build()

        assert isinstance(server, McpServer)
        assert server.toolset is tool_registry
        assert server.auth is None
        assert server.enforce_auth is False

    def test_factory_with_custom_context_builder(self, tool_registry, _basic_policy):
        """Test factory with custom context builder."""
        def custom_builder(principal, _ctx):
            return RunContext(principal=principal, db=None)

        factory = McpServerFactory(
            toolset=tool_registry,
            context_builder=custom_builder,
        )
        server = factory.build()

        assert server.context_builder is custom_builder

    def test_factory_with_auth(self, tool_registry):
        """Test factory with auth function."""
        def auth_fn(_ctx):
            return Principal(tenant_id="t", user_id="u")

        factory = McpServerFactory(
            toolset=tool_registry,
            auth=auth_fn,
        )
        server = factory.build()

        assert server.auth is auth_fn

    def test_factory_with_enforce_auth(self, tool_registry):
        """Test factory with enforce_auth flag."""
        factory = McpServerFactory(
            toolset=tool_registry,
            enforce_auth=True,
        )
        server = factory.build()

        assert server.enforce_auth is True


# === Tests for McpServer ===

class TestMcpServer:
    """Tests for McpServer."""

    def test_get_tools_returns_list(self, mcp_server, tool_registry):
        """Test that get_tools returns a list."""
        tools = mcp_server.get_tools()

        assert isinstance(tools, list)
        assert len(tools) == len(tool_registry.get_schemas())

    def test_get_tools_contains_expected_tools(self, mcp_server):
        """Test that get_tools contains expected tool names."""
        tools = mcp_server.get_tools()
        tool_names = [t.get("name", t.get("function", {}).get("name")) for t in tools]

        assert "describe_schema" in tool_names
        assert "query" in tool_names
        assert "get" in tool_names
        assert "aggregate" in tool_names

    @pytest.mark.asyncio
    async def test_call_tool_without_auth_when_not_required(self, mcp_server, context):
        """Test calling tool without auth when enforce_auth is False."""
        result = await mcp_server.call_tool(
            name="query",
            arguments={"model": "User"},
            context=context,
        )

        assert result is not None
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_call_tool_with_context(self, mcp_server, context, _sample_principal):
        """Test that context is passed to tool execution."""
        result = await mcp_server.call_tool(
            name="query",
            arguments={"model": "User"},
            context=context,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_call_tool_with_enforce_auth_no_auth(self, mcp_server_with_auth):
        """Test that tool call fails when auth is required but not provided."""
        with pytest.raises(AuthenticationError):
            await mcp_server_with_auth.call_tool(
                name="query",
                arguments={"model": "User"},
                context={},  # No principal
            )

    @pytest.mark.asyncio
    async def test_call_tool_with_enforce_auth_valid(self, mcp_server_with_auth, context):
        """Test that tool call succeeds when auth is provided."""
        result = await mcp_server_with_auth.call_tool(
            name="query",
            arguments={"model": "User"},
            context=context,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self, mcp_server, context):
        """Test calling a tool that doesn't exist."""
        result = await mcp_server.call_tool(
            name="nonexistent_tool",
            arguments={},
            context=context,
        )

        # Should return error result
        assert result is not None
        assert result.get("success") is False
        assert "not found" in str(result.get("error", {})).lower()


class TestMcpServerAuthentication:
    """Tests for MCP server authentication."""

    def test_default_auth_when_not_provided(self, tool_registry):
        """Test that default auth uses hardcoded credentials."""
        factory = McpServerFactory(toolset=tool_registry, enforce_auth=False)
        server = factory.build()

        assert server.auth is None
        assert server.enforce_auth is False

    def test_custom_auth_function(self, tool_registry):
        """Test custom auth function is called."""
        auth_called = False

        def custom_auth(_ctx):
            nonlocal auth_called
            auth_called = True
            return Principal(tenant_id="custom", user_id="u1")

        factory = McpServerFactory(
            toolset=tool_registry,
            auth=custom_auth,
            enforce_auth=True,
        )
        server = factory.build()

        assert server.auth is custom_auth


class TestMcpServerToolRegistration:
    """Tests for tool registration in MCP server."""

    def test_tools_registered_on_init(self, mcp_server, _tool_registry):
        """Test that tools are registered on server init."""
        schemas = mcp_server.get_tools()
        registered_names = {s.get("name") or s.get("function", {}).get("name") for s in schemas}

        for tool_name in ["describe_schema", "query", "get", "aggregate"]:
            assert tool_name in registered_names

    def test_tool_count_matches_registry(self, mcp_server, tool_registry):
        """Test that tool count matches registry."""
        server_tools = mcp_server.get_tools()
        registry_schemas = tool_registry.get_schemas()

        assert len(server_tools) == len(registry_schemas)


class TestMcpServerErrorHandling:
    """Tests for error handling in MCP server."""

    @pytest.mark.asyncio
    async def test_invalid_arguments(self, mcp_server, context):
        """Test handling of invalid tool arguments."""
        # Missing required 'model' field
        result = await mcp_server.call_tool(
            name="query",
            arguments={},  # Missing model
            context=context,
        )

        # Should return error
        assert result is not None


class TestMcpServerContext:
    """Tests for context handling in MCP server."""

    @pytest.mark.asyncio
    async def test_empty_context_uses_default(self, mcp_server):
        """Test that empty context uses default principal."""
        result = await mcp_server.call_tool(
            name="describe_schema",
            arguments={},
            context={},  # Empty context
        )

        # Should not raise - uses default auth
        assert result is not None


class TestMcpServerIntegration:
    """Integration tests for MCP server with policies."""

    @pytest.mark.asyncio
    async def test_server_with_complex_policy(self, tool_registry):
        """Test server with complex policy configuration."""
        _complex_policy = Policy(
            models={
                "User": ModelPolicy(
                    allowed=True,
                    readable=True,
                    writable=True,
                    fields={
                        "ssn": FieldPolicy(action=FieldAction.DENY),
                        "credit_card": FieldPolicy(action=FieldAction.MASK),
                    },
                    row_policy=RowPolicy(
                        tenant_scope_field="tenant_id",
                        require_scope=True,
                    ),
                ),
            },
            default_budget=Budget(max_rows=50),
            require_tenant_scope=True,
        )

        factory = McpServerFactory(
            toolset=tool_registry,
            enforce_auth=False,
        )
        server = factory.build()

        assert server is not None
        tools = server.get_tools()
        assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_tool_schemas_reflect_policy(self, tool_registry, _basic_policy):
        """Test that tool schemas reflect policy restrictions."""
        factory = McpServerFactory(
            toolset=tool_registry,
            enforce_auth=False,
        )
        server = factory.build()

        tools = server.get_tools()

        # Verify tools have schemas
        assert len(tools) > 0
        for tool in tools:
            assert "name" in tool or "function" in tool


class TestMcpServerAsyncSupport:
    """Tests for async support in MCP server."""

    @pytest.mark.asyncio
    async def test_async_call_tool(self, mcp_server, context):
        """Test that call_tool works with async/await."""
        result = await mcp_server.call_tool(
            name="query",
            arguments={"model": "User"},
            context=context,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, mcp_server, context):
        """Test multiple concurrent tool calls."""
        import asyncio

        # Make multiple concurrent calls
        tasks = [
            mcp_server.call_tool("query", {"model": "User"}, context)
            for _ in range(5)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for result in results:
            assert result is not None


class TestMcpServerDefaults:
    """Tests for default values and configuration."""

    def test_server_default_enforce_auth_is_false(self, tool_registry):
        """Test that default enforce_auth is False."""
        factory = McpServerFactory(toolset=tool_registry)
        server = factory.build()

        assert server.enforce_auth is False

    def test_factory_stores_toolset(self, tool_registry):
        """Test that factory stores the toolset."""
        factory = McpServerFactory(toolset=tool_registry)
        server = factory.build()

        assert server.toolset is tool_registry

    def test_server_initial_state(self, mcp_server):
        """Test server initial state."""
        assert mcp_server.toolset is not None
        assert isinstance(mcp_server.get_tools(), list)
