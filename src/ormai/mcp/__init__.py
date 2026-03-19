"""
OrmAI MCP Module.

Provides MCP server integration for exposing OrmAI tools via the Model Context Protocol.

Note: Full MCP integration requires the 'mcp' package.
Install with: uv add ormai[mcp]
"""

from ormai.mcp.config import (
    McpClientType,
    McpConfigGenerator,
    McpServerConfig,
    McpTemplates,
    OrmAIServerConfig,
    get_claude_desktop_config_path,
    install_claude_desktop,
)
from ormai.mcp.server import McpServerFactory

__all__ = [
    # Server
    "McpServerFactory",
    # Config
    "McpServerConfig",
    "OrmAIServerConfig",
    "McpConfigGenerator",
    "McpClientType",
    "McpTemplates",
    # Helpers
    "get_claude_desktop_config_path",
    "install_claude_desktop",
]
