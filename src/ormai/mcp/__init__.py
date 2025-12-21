"""
OrmAI MCP Module.

Provides MCP server integration for exposing OrmAI tools via the Model Context Protocol.

Note: Full MCP integration requires the 'mcp' package.
Install with: uv add ormai[mcp]
"""

from ormai.mcp.server import McpServerFactory

__all__ = [
    "McpServerFactory",
]
