"""
Tool registry for managing available tools.
"""

from __future__ import annotations

from typing import Any

from ormai.core.context import RunContext
from ormai.tools.base import Tool, ToolResult


class ToolRegistry:
    """
    Registry for managing OrmAI tools.

    The registry:
    - Stores available tools by name
    - Provides tool discovery for LLMs
    - Routes tool calls to implementations
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def all(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    async def execute(
        self,
        name: str,
        input: dict[str, Any],
        ctx: RunContext,
    ) -> ToolResult:
        """
        Execute a tool by name.

        Returns a ToolResult with the output or error.
        """
        tool = self.get(name)
        if tool is None:
            return ToolResult.fail({
                "code": "TOOL_NOT_FOUND",
                "message": f"Tool '{name}' not found",
                "retry_hints": [f"Available tools: {', '.join(self.list())}"],
            })

        return await tool.run(input, ctx)

    def get_schemas(self) -> list[dict[str, Any]]:
        """
        Get JSON schemas for all registered tools.

        Used for LLM tool descriptions and MCP exposure.
        """
        return [tool.get_json_schema() for tool in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
