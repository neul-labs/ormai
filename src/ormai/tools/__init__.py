"""
OrmAI Tools Module.

Provides the tool runtime, generic DB tools, and domain tool registration.
"""

from ormai.tools.base import Tool, ToolResult
from ormai.tools.deferred import DeferredExecutor, DeferredResult, require_approval_or_raise
from ormai.tools.generic import (
    AggregateInput,
    AggregateTool,
    BulkUpdateInput,
    BulkUpdateTool,
    CreateInput,
    CreateTool,
    DeleteInput,
    DeleteTool,
    DescribeSchemaInput,
    DescribeSchemaTool,
    GetInput,
    GetTool,
    QueryInput,
    QueryTool,
    UpdateInput,
    UpdateTool,
)
from ormai.tools.registry import ToolRegistry

__all__ = [
    # Base
    "Tool",
    "ToolResult",
    # Registry
    "ToolRegistry",
    # Generic read tools
    "DescribeSchemaInput",
    "DescribeSchemaTool",
    "QueryInput",
    "QueryTool",
    "GetInput",
    "GetTool",
    "AggregateInput",
    "AggregateTool",
    # Generic write tools
    "CreateInput",
    "CreateTool",
    "UpdateInput",
    "UpdateTool",
    "DeleteInput",
    "DeleteTool",
    "BulkUpdateInput",
    "BulkUpdateTool",
    # Deferred execution
    "DeferredExecutor",
    "DeferredResult",
    "require_approval_or_raise",
]
