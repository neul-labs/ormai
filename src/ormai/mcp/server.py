"""
MCP server factory.

Creates MCP servers that expose OrmAI tools.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ormai.core.context import Principal, RunContext
from ormai.core.errors import AuthenticationError
from ormai.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Default principal constants for development use
DEFAULT_DEV_TENANT = "default"
DEFAULT_DEV_USER = "anonymous"


class McpServerFactory:
    """
    Factory for creating MCP servers from OrmAI toolsets.

    The MCP server exposes all registered tools with their JSON schemas,
    handles authentication, and routes tool calls to implementations.

    Security Note:
        If no auth function is provided and enforce_auth is True, an
        AuthenticationError will be raised. Set enforce_auth=False for
        development only. Always provide an auth function in production.

    Example:
        server = McpServerFactory(
            toolset=toolset,
            auth=jwt_auth,
            context_builder=default_context_builder,
            enforce_auth=True,
        ).build()
    """

    def __init__(
        self,
        toolset: ToolRegistry,
        auth: Callable[[dict[str, Any]], Principal] | None = None,
        context_builder: Callable[[Principal, Any], RunContext] | None = None,
        enforce_auth: bool = False,
    ) -> None:
        """
        Initialize the factory.

        Args:
            toolset: The tool registry to expose
            auth: Optional auth function that extracts Principal from request
            context_builder: Optional function to build RunContext from Principal
            enforce_auth: If True, require auth function or raise AuthenticationError
        """
        self.toolset = toolset
        self.auth = auth
        self.context_builder = context_builder
        self.enforce_auth = enforce_auth

    def build(self) -> McpServer:
        """
        Build the MCP server.

        Returns an McpServer instance ready to handle requests.
        """
        return McpServer(
            toolset=self.toolset,
            auth=self.auth,
            context_builder=self.context_builder,
            enforce_auth=self.enforce_auth,
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
        enforce_auth: bool = False,
    ) -> None:
        self.toolset = toolset
        self.auth = auth
        self.context_builder = context_builder
        self.enforce_auth = enforce_auth

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
            if self.enforce_auth:
                raise AuthenticationError(
                    "Authentication required but no auth function provided. "
                    "Provide an auth function or set enforce_auth=False for development."
                )
            # Default principal for development - warn about security implications
            logger.warning(
                "No auth function provided. Using default development principal "
                "(tenant_id=%r, user_id=%r). This is insecure for production use. "
                "Provide an auth function or set enforce_auth=True to enforce authentication.",
                DEFAULT_DEV_TENANT,
                DEFAULT_DEV_USER,
            )
            principal = Principal(
                tenant_id=DEFAULT_DEV_TENANT,
                user_id=DEFAULT_DEV_USER,
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
        except ImportError as err:
            raise ImportError(
                "MCP SDK not installed. Install with: uv add ormai[mcp]"
            ) from err

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
