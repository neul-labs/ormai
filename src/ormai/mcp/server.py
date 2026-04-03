"""
MCP server factory.

Creates MCP servers that expose OrmAI tools.
"""
from __future__ import annotations

import logging
import os
import warnings
from collections.abc import Callable
from typing import Any

from ormai.core.context import Principal, RunContext
from ormai.core.errors import AuthenticationError
from ormai.middleware.rate_limit import RateLimiter
from ormai.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Environment detection
ORMAI_ENV = os.getenv("ORMAI_ENV", "production").lower()
IS_PRODUCTION = ORMAI_ENV == "production"
IS_DEVELOPMENT = ORMAI_ENV == "development"

# Default principal constants for development use only
# WARNING: These should NEVER be used in production
_DEV_TENANT = "dev-default"
_DEV_USER = "dev-anonymous"


def _is_production_environment() -> bool:
    """
    Detect if running in a production environment.

    Checks ORMAI_ENV environment variable:
    - "production" (default): Returns True
    - "development": Returns False
    - Any other value: Returns True (fail-safe)
    """
    return not IS_DEVELOPMENT


class McpServerFactory:
    """
    Factory for creating MCP servers from OrmAI toolsets.

    The MCP server exposes all registered tools with their JSON schemas,
    handles authentication, and routes tool calls to implementations.

    Security Note:
        By default, enforce_auth is automatically determined based on ORMAI_ENV:
        - production (default): enforce_auth=True (requires auth function)
        - development: enforce_auth=False (allows anonymous access with warnings)

        Always provide an auth function in production. Set ORMAI_ENV=development
        only for local development and testing.

    Example:
        # Production (requires auth)
        server = McpServerFactory(
            toolset=toolset,
            auth=jwt_auth,
            context_builder=default_context_builder,
        ).build()

        # Development (set ORMAI_ENV=development)
        server = McpServerFactory(toolset=toolset).build()
    """

    def __init__(
        self,
        toolset: ToolRegistry,
        auth: Callable[[dict[str, Any]], Principal] | None = None,
        context_builder: Callable[[Principal, Any], RunContext] | None = None,
        enforce_auth: bool | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """
        Initialize the factory.

        Args:
            toolset: The tool registry to expose
            auth: Optional auth function that extracts Principal from request
            context_builder: Optional function to build RunContext from Principal
            enforce_auth: If True, require auth function. If None (default),
                         auto-detect based on ORMAI_ENV environment variable.
            rate_limiter: Optional rate limiter for request throttling
        """
        self.toolset = toolset
        self.auth = auth
        self.context_builder = context_builder
        self.rate_limiter = rate_limiter

        # Auto-detect enforce_auth based on environment if not explicitly set
        if enforce_auth is None:
            self.enforce_auth = _is_production_environment()
            if self.enforce_auth and not auth:
                logger.warning(
                    "Running in production mode (ORMAI_ENV=%s) without auth function. "
                    "Set ORMAI_ENV=development for local development, or provide an "
                    "auth function for production use.",
                    ORMAI_ENV,
                )
        else:
            self.enforce_auth = enforce_auth
            if not enforce_auth and _is_production_environment():
                warnings.warn(
                    "enforce_auth=False in production environment. This is insecure. "
                    "Consider setting ORMAI_ENV=development for local development.",
                    UserWarning,
                    stacklevel=2,
                )

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
            rate_limiter=self.rate_limiter,
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
        enforce_auth: bool | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.toolset = toolset
        self.auth = auth
        self.context_builder = context_builder
        self.rate_limiter = rate_limiter
        # Use provided value or auto-detect from environment
        self.enforce_auth = enforce_auth if enforce_auth is not None else _is_production_environment()

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
                    "Set ORMAI_ENV=development for local development, or provide "
                    "an auth function for production use."
                )
            # Default principal for development only
            if _is_production_environment():
                logger.error(
                    "SECURITY WARNING: Using development principal in production! "
                    "Set ORMAI_ENV=development or provide an auth function."
                )
            else:
                logger.info(
                    "Using development principal (tenant_id=%r, user_id=%r). "
                    "This is expected in development mode (ORMAI_ENV=development).",
                    _DEV_TENANT,
                    _DEV_USER,
                )
            principal = Principal(
                tenant_id=_DEV_TENANT,
                user_id=_DEV_USER,
            )

        # Check rate limits if enabled
        if self.rate_limiter:
            await self.rate_limiter.check_and_raise(principal, tool_name=name)

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
