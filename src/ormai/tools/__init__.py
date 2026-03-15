"""
OrmAI Tools Module.

Provides the tool runtime, generic DB tools, and domain tool registration.
"""

from ormai.tools.base import Tool, ToolResult
from ormai.tools.generic import (
    AggregateInput,
    AggregateTool,
    DescribeSchemaInput,
    DescribeSchemaTool,
    GetInput,
    GetTool,
    QueryInput,
    QueryTool,
)
from ormai.tools.registry import ToolRegistry

__all__ = [
    # Base
    "Tool",
    "ToolResult",
    # Registry
    "ToolRegistry",
    # Generic tools
    "DescribeSchemaInput",
    "DescribeSchemaTool",
    "QueryInput",
    "QueryTool",
    "GetInput",
    "GetTool",
    "AggregateInput",
    "AggregateTool",
]
