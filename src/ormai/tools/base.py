"""
Base tool class and result types.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from ormai.core.context import RunContext

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT")


class ToolResult(BaseModel, Generic[OutputT]):
    """
    Result of a tool execution.
    """

    success: bool
    data: OutputT | None = None
    error: dict[str, Any] | None = None

    model_config = {"frozen": True}

    @classmethod
    def ok(cls, data: OutputT) -> "ToolResult[OutputT]":
        """Create a successful result."""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: dict[str, Any]) -> "ToolResult[OutputT]":
        """Create a failed result."""
        return cls(success=False, error=error)


class Tool(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for OrmAI tools.

    Tools are the primary interface for agents to interact with the database.
    Each tool:
    - Has a name and description for LLM consumption
    - Defines a Pydantic input schema
    - Executes within a RunContext with policy enforcement
    - Returns a typed result
    """

    # Tool metadata
    name: str
    description: str

    # Input schema class
    input_schema: type[InputT]

    @abstractmethod
    async def execute(
        self,
        input: InputT,
        ctx: RunContext,
    ) -> OutputT:
        """
        Execute the tool with the given input and context.

        Implementations should:
        1. Validate input against policies
        2. Execute the operation
        3. Apply any post-processing (redaction, etc.)
        4. Return the result

        Raises OrmAIError subclasses for policy violations.
        """
        ...

    async def run(
        self,
        input: InputT | dict[str, Any],
        ctx: RunContext,
    ) -> ToolResult[OutputT]:
        """
        Run the tool with error handling.

        This is the main entry point for tool execution.
        Returns a ToolResult wrapping the output or error.
        """
        try:
            # Validate input if dict
            if isinstance(input, dict):
                input = self.input_schema.model_validate(input)

            result = await self.execute(input, ctx)
            return ToolResult.ok(result)

        except Exception as e:
            from ormai.core.errors import OrmAIError

            if isinstance(e, OrmAIError):
                return ToolResult.fail(e.to_dict())
            else:
                return ToolResult.fail({
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                })

    def get_json_schema(self) -> dict[str, Any]:
        """
        Get the JSON schema for this tool's input.

        Used for LLM tool descriptions and MCP exposure.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema.model_json_schema(),
        }
