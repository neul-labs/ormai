"""
LangGraph integration for OrmAI.

Provides tools compatible with LangGraph and LangChain.
"""

from collections.abc import Callable
from typing import Any

from ormai.core.context import Principal, RunContext
from ormai.tools.registry import ToolRegistry

try:
    from langchain_core.tools import BaseTool, StructuredTool
    from pydantic import BaseModel, Field, create_model
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    BaseTool = object  # type: ignore
    StructuredTool = None  # type: ignore


def ormai_to_langchain_tool(
    tool: Any,
    get_context: Callable[[], RunContext] | None = None,
    context: RunContext | None = None,
) -> Any:
    """
    Convert an OrmAI tool to a LangChain/LangGraph tool.

    Args:
        tool: The OrmAI tool instance
        get_context: Function to get RunContext for each call
        context: Static context to use for all calls

    Returns:
        A LangChain StructuredTool
    """
    if not HAS_LANGCHAIN:
        raise ImportError(
            "LangChain is not installed. Install with: pip install langchain-core"
        )

    schema = tool.get_schema()

    # Build Pydantic model for input validation
    input_schema = _schema_to_pydantic(schema["parameters"])

    async def _call_tool(**kwargs: Any) -> dict[str, Any]:
        """Call the OrmAI tool."""
        # Get context
        if get_context:
            ctx = get_context()
        elif context:
            ctx = context
        else:
            ctx = RunContext(
                principal=Principal(tenant_id="default", user_id="anonymous")
            )

        # Execute tool
        result = await tool.execute(kwargs, ctx)
        return result.model_dump()

    return StructuredTool.from_function(
        func=_call_tool,
        name=schema["name"],
        description=schema["description"],
        args_schema=input_schema,
        coroutine=_call_tool,
    )


def ormai_toolset_to_langchain(
    toolset: ToolRegistry,
    get_context: Callable[[], RunContext] | None = None,
    context: RunContext | None = None,
) -> list[Any]:
    """
    Convert an OrmAI toolset to LangChain/LangGraph tools.

    Args:
        toolset: The OrmAI tool registry
        get_context: Function to get RunContext for each call
        context: Static context to use for all calls

    Returns:
        List of LangChain StructuredTool instances
    """
    if not HAS_LANGCHAIN:
        raise ImportError(
            "LangChain is not installed. Install with: pip install langchain-core"
        )

    tools = []
    for tool in toolset.tools.values():
        lc_tool = ormai_to_langchain_tool(tool, get_context, context)
        tools.append(lc_tool)

    return tools


def _schema_to_pydantic(schema: dict[str, Any]) -> type[BaseModel]:
    """Convert a JSON schema to a Pydantic model."""
    if not HAS_LANGCHAIN:
        raise ImportError("LangChain/Pydantic is required")

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    fields = {}
    for name, prop in properties.items():
        field_type = _json_type_to_python(prop.get("type", "string"))
        description = prop.get("description", "")

        if name in required:
            fields[name] = (field_type, Field(description=description))
        else:
            fields[name] = (field_type | None, Field(default=None, description=description))

    return create_model("ToolInput", **fields)


def _json_type_to_python(json_type: str) -> type:
    """Convert JSON schema type to Python type."""
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_map.get(json_type, str)


class OrmAIToolkit:
    """
    LangGraph-compatible toolkit for OrmAI.

    Provides tools for database operations that can be used with LangGraph agents.

    Usage:
        from langgraph.prebuilt import create_react_agent
        from ormai.integrations.langgraph import OrmAIToolkit

        toolkit = OrmAIToolkit(toolset)
        agent = create_react_agent(llm, toolkit.get_tools())
    """

    def __init__(
        self,
        toolset: ToolRegistry,
        get_context: Callable[[], RunContext] | None = None,
    ) -> None:
        """
        Initialize the toolkit.

        Args:
            toolset: The OrmAI tool registry
            get_context: Function to get RunContext for each call
        """
        if not HAS_LANGCHAIN:
            raise ImportError(
                "LangChain is not installed. Install with: pip install langchain-core"
            )

        self.toolset = toolset
        self.get_context = get_context
        self._tools: list[Any] | None = None

    def get_tools(self) -> list[Any]:
        """Get all tools as LangChain tools."""
        if self._tools is None:
            self._tools = ormai_toolset_to_langchain(
                self.toolset,
                get_context=self.get_context,
            )
        return self._tools

    def get_tool(self, name: str) -> Any | None:
        """Get a specific tool by name."""
        for tool in self.get_tools():
            if tool.name == name:
                return tool
        return None


def create_ormai_toolkit(
    toolset: ToolRegistry,
    get_context: Callable[[], RunContext] | None = None,
) -> OrmAIToolkit:
    """
    Create a LangGraph-compatible toolkit from OrmAI toolset.

    Usage:
        from ormai.integrations.langgraph import create_ormai_toolkit

        toolkit = create_ormai_toolkit(toolset)
        tools = toolkit.get_tools()
    """
    return OrmAIToolkit(toolset, get_context)
