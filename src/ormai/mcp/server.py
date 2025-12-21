"""
MCP server factory.

Creates MCP servers that expose OrmAI tools.
"""

from collections.abc import Callable
from typing import Any

from ormai.core.context import Principal, RunContext
from ormai.tools.registry import ToolRegistry


class McpServerFactory:
    """
    Factory for creating MCP servers from OrmAI toolsets.

    The MCP server exposes all registered tools with their JSON schemas,
    handles authentication, and routes tool calls to implementations.

    Example:
        server = McpServerFactory(
            toolset=toolset,
            auth=jwt_auth,
            context_builder=default_context_builder,
        ).build()
    """

    def __init__(
        self,
        toolset: ToolRegistry,
        auth: Callable[[dict[str, Any]], Principal] | None = None,
        context_builder: Callable[[Principal, Any], RunContext] | None = None,
    ) -> None:
        """
        Initialize the factory.

        Args:
            toolset: The tool registry to expose
            auth: Optional auth function that extracts Principal from request
            context_builder: Optional function to build RunContext from Principal
        """
        self.toolset = toolset
        self.auth = auth
        self.context_builder = context_builder

    def build(self) -> "McpServer":
        """
        Build the MCP server.

        Returns an McpServer instance ready to handle requests.
        """
        return McpServer(
            toolset=self.toolset,
            auth=self.auth,
            context_builder=self.context_builder,
        )


class McpServer:
    """
    MCP server implementation.

    Handles MCP protocol requests and routes them to OrmAI tools.
    """

    def __init__(
        self,
        toolset: ToolRegistry,
        auth: Callable[[dict[str, Any]], Principal] | None = None,
        context_builder: Callable[[Principal, Any], RunContext] | None = None,
    ) -> None:
        self.toolset = toolset
        self.auth = auth
        self.context_builder = context_builder

    def get_tools(self) -> list[dict[str, Any]]:
        """
        Get the list of available tools with their schemas.

        Returns tool definitions in MCP format.
        """
        return self.toolset.get_schemas()

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Call a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments
            context: Optional context (auth info, session, etc.)

        Returns the tool result.
        """
        # Build principal from auth
        if self.auth and context:
            principal = self.auth(context)
        else:
            # Default principal for development
            principal = Principal(
                tenant_id="default",
                user_id="anonymous",
            )

        # Build run context
        if self.context_builder and context:
            ctx = self.context_builder(principal, context.get("db"))
        else:
            ctx = RunContext(
                principal=principal,
                db=context.get("db") if context else None,
            )

        # Execute tool
        result = await self.toolset.execute(name, arguments, ctx)
        return result.model_dump()

    def to_mcp_server(self) -> Any:
        """
        Convert to an MCP SDK server instance.

        Requires the 'mcp' package to be installed.
        Returns an mcp.Server instance configured with OrmAI tools.
        """
        try:
            from mcp.server import Server
            from mcp.types import Tool as McpTool
        except ImportError:
            raise ImportError(
                "MCP SDK not installed. Install with: uv add ormai[mcp]"
            )

        server = Server("ormai")

        # Register tools
        @server.list_tools()
        async def list_tools() -> list[McpTool]:
            tools = []
            for schema in self.get_tools():
                tools.append(
                    McpTool(
                        name=schema["name"],
                        description=schema["description"],
                        inputSchema=schema["parameters"],
                    )
                )
            return tools

        @server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> Any:
            result = await self.call_tool(name, arguments)
            return result

        return server
