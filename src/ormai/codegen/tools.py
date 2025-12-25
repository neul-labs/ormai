"""
Domain tool code generator.

Generates typed domain tool source files from ORM metadata and policies.
"""

from datetime import datetime

from ormai.codegen.generator import CodeGenerator, GeneratedFile, GenerationResult
from ormai.core.types import ModelMetadata, SchemaMetadata
from ormai.policy.models import ModelPolicy, Policy


class DomainToolGenerator(CodeGenerator):
    """
    Generates domain-specific tool source code.

    Produces Python files with typed, model-specific tools that:
    - Are named after the domain model (e.g., get_customer, list_orders)
    - Have properly typed input/output schemas
    - Include docstrings derived from model metadata
    - Wrap the generic tools with model-specific logic

    Example output:
        class GetCustomerInput(BaseModel):
            id: int

        async def get_customer(ctx: RunContext, input: GetCustomerInput) -> CustomerView:
            '''Get a customer by ID.'''
            ...
    """

    def __init__(
        self,
        schema: SchemaMetadata,
        policy: Policy,
        *,
        module_name: str = "domain_tools",
        views_module: str = "views",
    ) -> None:
        """
        Initialize the generator.

        Args:
            schema: Database schema metadata
            policy: Policy configuration
            module_name: Name for the generated module
            views_module: Module name where views are defined
        """
        super().__init__(schema, policy)
        self.module_name = module_name
        self.views_module = views_module

    def generate(self) -> GenerationResult:
        """Generate domain tool source files."""
        result = GenerationResult()

        # Generate main tools file
        tools_content = self._generate_tools_file()
        result.files.append(GeneratedFile(
            path=f"{self.module_name}.py",
            content=tools_content,
            module_name=self.module_name,
        ))

        return result

    def _generate_tools_file(self) -> str:
        """Generate the main tools file content."""
        # Collect all model names for imports
        model_names = list(self.policy.list_allowed_models())

        lines = [
            '"""',
            "Auto-generated domain tools.",
            "",
            f"Generated at: {datetime.utcnow().isoformat()}",
            "Do not edit manually - regenerate from schema/policy changes.",
            '"""',
            "",
            "from __future__ import annotations",
            "",
            "from typing import Any",
            "",
            "from pydantic import BaseModel, Field",
            "",
            "from ormai.core.context import RunContext",
            "from ormai.core.dsl import (",
            "    CreateRequest,",
            "    DeleteRequest,",
            "    GetRequest,",
            "    QueryRequest,",
            "    UpdateRequest,",
            ")",
            "from ormai.adapters.base import OrmAdapter",
            "from ormai.policy.models import Policy",
            "from ormai.core.types import SchemaMetadata",
            "",
        ]

        # Import views
        if model_names:
            view_imports = ", ".join(f"{name}View" for name in model_names)
            lines.append(f"from {self.views_module} import {view_imports}")
            lines.append("")

        lines.append("")

        # Generate tools for each model
        for model_name in model_names:
            model_meta = self.schema.get_model(model_name)
            if model_meta is None:
                continue

            model_policy = self.policy.get_model_policy(model_name)

            # Generate input schemas
            lines.extend(self._generate_input_schemas(model_name, model_meta))
            lines.append("")

            # Generate tool class
            lines.extend(self._generate_tool_class(model_name, model_meta, model_policy))
            lines.append("")

        return "\n".join(lines)

    def _generate_input_schemas(
        self,
        model_name: str,
        model_meta: ModelMetadata,
    ) -> list[str]:
        """Generate input schemas for a model's tools."""
        snake_name = self._to_snake_case(model_name)
        lines = []

        # Get input
        lines.extend([
            f"class Get{model_name}Input(BaseModel):",
            f'    """Input for getting a single {model_name}."""',
            "",
            f"    id: int = Field(..., description=\"ID of the {model_name} to retrieve\")",
            "",
        ])

        # List input
        lines.extend([
            f"class List{model_name}Input(BaseModel):",
            f'    """Input for listing {model_name} records."""',
            "",
            "    limit: int = Field(default=10, ge=1, le=100, description=\"Maximum records to return\")",
            "    offset: int = Field(default=0, ge=0, description=\"Number of records to skip\")",
            "    order_by: str | None = Field(default=None, description=\"Field to order by\")",
            "",
        ])

        return lines

    def _generate_tool_class(
        self,
        model_name: str,
        model_meta: ModelMetadata,
        model_policy: ModelPolicy | None,
    ) -> list[str]:
        """Generate a domain tool class for a model."""
        snake_name = self._to_snake_case(model_name)
        lines = []

        lines.extend([
            f"class {model_name}Tools:",
            f'    """Domain tools for {model_name} operations."""',
            "",
            "    def __init__(",
            "        self,",
            "        adapter: OrmAdapter,",
            "        policy: Policy,",
            "        schema: SchemaMetadata,",
            "    ) -> None:",
            "        self.adapter = adapter",
            "        self.policy = policy",
            "        self.schema = schema",
            "",
        ])

        # Get method
        lines.extend([
            f"    async def get_{snake_name}(",
            "        self,",
            "        ctx: RunContext,",
            f"        input: Get{model_name}Input,",
            f"    ) -> {model_name}View | None:",
            f'        """',
            f"        Get a {model_name} by ID.",
            "",
            "        Args:",
            f"            ctx: Run context with principal and session",
            f"            input: Input containing the {model_name} ID",
            "",
            "        Returns:",
            f"            {model_name}View if found, None otherwise",
            '        """',
            f"        request = GetRequest(model=\"{model_name}\", id=input.id)",
            "        compiled = self.adapter.compile_get(request, ctx, self.policy, self.schema)",
            "        result = await self.adapter.execute_get(compiled, ctx)",
            "        if result.data is None:",
            "            return None",
            f"        return {model_name}View.model_validate(result.data)",
            "",
        ])

        # List method
        lines.extend([
            f"    async def list_{snake_name}s(",
            "        self,",
            "        ctx: RunContext,",
            f"        input: List{model_name}Input,",
            f"    ) -> list[{model_name}View]:",
            f'        """',
            f"        List {model_name} records.",
            "",
            "        Args:",
            f"            ctx: Run context with principal and session",
            f"            input: Input with pagination options",
            "",
            "        Returns:",
            f"            List of {model_name}View records",
            '        """',
            "        order_by = None",
            "        if input.order_by:",
            "            order_by = [{\"field\": input.order_by, \"direction\": \"asc\"}]",
            "",
            f"        request = QueryRequest(",
            f'            model="{model_name}",',
            "            take=input.limit,",
            "            skip=input.offset,",
            "            order_by=order_by,",
            "        )",
            "        compiled = self.adapter.compile_query(request, ctx, self.policy, self.schema)",
            "        result = await self.adapter.execute_query(compiled, ctx)",
            f"        return [{model_name}View.model_validate(row) for row in result.data]",
            "",
        ])

        # Add mutation methods if writable
        if model_policy and model_policy.writable:
            lines.extend(self._generate_mutation_methods(model_name, model_meta, model_policy))

        return lines

    def _generate_mutation_methods(
        self,
        model_name: str,
        model_meta: ModelMetadata,
        model_policy: ModelPolicy,
    ) -> list[str]:
        """Generate mutation methods for a writable model."""
        snake_name = self._to_snake_case(model_name)
        lines = []

        # Create method
        if model_policy.write_policy and model_policy.write_policy.allow_create:
            lines.extend([
                f"    async def create_{snake_name}(",
                "        self,",
                "        ctx: RunContext,",
                "        data: dict[str, Any],",
                "        reason: str | None = None,",
                f"    ) -> {model_name}View:",
                f'        """',
                f"        Create a new {model_name}.",
                "",
                "        Args:",
                f"            ctx: Run context with principal and session",
                f"            data: Data for the new {model_name}",
                "            reason: Optional reason for the operation",
                "",
                "        Returns:",
                f"            Created {model_name}View",
                '        """',
                f"        request = CreateRequest(model=\"{model_name}\", data=data, reason=reason)",
                "        compiled = self.adapter.compile_create(request, ctx, self.policy, self.schema)",
                "        result = await self.adapter.execute_create(compiled, ctx)",
                f"        return {model_name}View.model_validate(result.data)",
                "",
            ])

        # Update method
        if model_policy.write_policy and model_policy.write_policy.allow_update:
            lines.extend([
                f"    async def update_{snake_name}(",
                "        self,",
                "        ctx: RunContext,",
                "        id: int,",
                "        data: dict[str, Any],",
                "        reason: str | None = None,",
                f"    ) -> {model_name}View | None:",
                f'        """',
                f"        Update a {model_name}.",
                "",
                "        Args:",
                f"            ctx: Run context with principal and session",
                f"            id: ID of the {model_name} to update",
                "            data: Fields to update",
                "            reason: Optional reason for the operation",
                "",
                "        Returns:",
                f"            Updated {model_name}View if found, None otherwise",
                '        """',
                f"        request = UpdateRequest(model=\"{model_name}\", id=id, data=data, reason=reason)",
                "        compiled = self.adapter.compile_update(request, ctx, self.policy, self.schema)",
                "        result = await self.adapter.execute_update(compiled, ctx)",
                "        if not result.found:",
                "            return None",
                f"        return {model_name}View.model_validate(result.data)",
                "",
            ])

        # Delete method
        if model_policy.write_policy and model_policy.write_policy.allow_delete:
            lines.extend([
                f"    async def delete_{snake_name}(",
                "        self,",
                "        ctx: RunContext,",
                "        id: int,",
                "        reason: str | None = None,",
                "        hard: bool = False,",
                "    ) -> bool:",
                f'        """',
                f"        Delete a {model_name}.",
                "",
                "        Args:",
                f"            ctx: Run context with principal and session",
                f"            id: ID of the {model_name} to delete",
                "            reason: Optional reason for the operation",
                "            hard: If True, permanently delete; otherwise soft-delete",
                "",
                "        Returns:",
                f"            True if {model_name} was found and deleted",
                '        """',
                f"        request = DeleteRequest(model=\"{model_name}\", id=id, reason=reason, hard=hard)",
                "        compiled = self.adapter.compile_delete(request, ctx, self.policy, self.schema)",
                "        result = await self.adapter.execute_delete(compiled, ctx)",
                "        return result.found",
                "",
            ])

        return lines

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case."""
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result)
