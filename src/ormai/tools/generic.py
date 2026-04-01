"""
Generic database tools.

These are the core tools that provide structured access to the database.
"""

from typing import Any

from pydantic import BaseModel, Field

from ormai.adapters.base import OrmAdapter
from ormai.core.context import RunContext
from ormai.core.dsl import (
    AggregateRequest,
    AggregateResult,
    BulkUpdateRequest,
    BulkUpdateResult,
    CreateRequest,
    CreateResult,
    DeleteRequest,
    DeleteResult,
    FilterClause,
    GetRequest,
    GetResult,
    IncludeClause,
    OrderClause,
    QueryRequest,
    QueryResult,
    UpdateRequest,
    UpdateResult,
)
from ormai.core.types import ModelMetadata, SchemaMetadata
from ormai.policy.models import ModelPolicy, Policy
from ormai.tools.base import Tool

# === Describe Schema Tool ===


class DescribeSchemaInput(BaseModel):
    """Input for describe_schema tool."""

    model: str | None = Field(
        default=None,
        description="Optional model name to get schema for. If not provided, returns all allowed models.",
    )


class SchemaDescription(BaseModel):
    """Output of describe_schema tool."""

    models: dict[str, Any] = Field(default_factory=dict)


class DescribeSchemaTool(Tool[DescribeSchemaInput, SchemaDescription]):
    """
    Tool to describe the database schema.

    Returns information about allowed models, fields, and relations
    based on the current policy.
    """

    name = "db.describe_schema"
    description = "Get the database schema including allowed models, fields, and relations."
    input_schema = DescribeSchemaInput

    def __init__(self, schema: SchemaMetadata, policy: Policy) -> None:
        self.schema = schema
        self.policy = policy

    async def execute(
        self,
        input: DescribeSchemaInput,
        ctx: RunContext,  # noqa: ARG002
    ) -> SchemaDescription:
        """Execute the describe_schema operation."""
        result: dict[str, Any] = {}

        if input.model:
            # Describe a specific model
            model_meta = self.schema.get_model(input.model)
            model_policy = self.policy.get_model_policy(input.model)

            if model_meta and model_policy and model_policy.allowed:
                result[input.model] = self._describe_model(model_meta, model_policy)
        else:
            # Describe all allowed models
            for model_name in self.policy.list_allowed_models():
                model_meta = self.schema.get_model(model_name)
                model_policy = self.policy.get_model_policy(model_name)

                if model_meta and model_policy:
                    result[model_name] = self._describe_model(model_meta, model_policy)

        return SchemaDescription(models=result)

    def _describe_model(
        self, model_meta: ModelMetadata, model_policy: ModelPolicy
    ) -> dict[str, Any]:
        """Build description for a single model."""
        # Get allowed fields
        fields = {}
        for field_name, field_meta in model_meta.fields.items():
            if model_policy.is_field_allowed(field_name):
                fields[field_name] = {
                    "type": field_meta.field_type.value,
                    "nullable": field_meta.nullable,
                    "primary_key": field_meta.primary_key,
                }

        # Get allowed relations
        relations = {}
        for rel_name, rel_meta in model_meta.relations.items():
            rel_policy = model_policy.relations.get(rel_name)
            if rel_policy is None or rel_policy.allowed:
                relations[rel_name] = {
                    "target": rel_meta.target_model,
                    "type": rel_meta.relation_type,
                }

        return {
            "table": model_meta.table_name,
            "fields": fields,
            "relations": relations,
            "readable": model_policy.readable,
            "writable": model_policy.writable,
        }


# === Query Tool ===


class QueryInput(BaseModel):
    """Input for query tool."""

    model: str = Field(..., description="The model to query")
    select: list[str] | None = Field(
        default=None, description="Fields to select (defaults to all allowed)"
    )
    where: list[dict[str, Any]] | None = Field(
        default=None, description="Filter conditions"
    )
    order_by: list[dict[str, Any]] | None = Field(
        default=None, description="Sort order"
    )
    take: int = Field(default=25, ge=1, le=100, description="Max rows to return")
    cursor: str | None = Field(default=None, description="Pagination cursor")
    include: list[dict[str, Any]] | None = Field(
        default=None, description="Relations to include"
    )


class QueryTool(Tool[QueryInput, QueryResult]):
    """
    Tool to query database records.

    Supports filtering, ordering, pagination, and relation includes.
    All queries are scoped and policy-enforced.
    """

    name = "db.query"
    description = "Query database records with filtering, ordering, and pagination."
    input_schema = QueryInput

    def __init__(self, adapter: OrmAdapter, policy: Policy, schema: SchemaMetadata) -> None:
        self.adapter = adapter
        self.policy = policy
        self.schema = schema

    async def execute(
        self,
        input: QueryInput,
        ctx: RunContext,
    ) -> QueryResult:
        """Execute the query operation."""
        # Build the request
        request = QueryRequest(
            model=input.model,
            select=input.select,
            where=[FilterClause.model_validate(f) for f in input.where] if input.where else None,
            order_by=[OrderClause.model_validate(o) for o in input.order_by] if input.order_by else None,
            take=input.take,
            cursor=input.cursor,
            include=[IncludeClause.model_validate(i) for i in input.include] if input.include else None,
        )

        # Compile and execute
        compiled = self.adapter.compile_query(request, ctx, self.policy, self.schema)
        return await self.adapter.execute_query(compiled, ctx)


# === Get Tool ===


class GetInput(BaseModel):
    """Input for get tool."""

    model: str = Field(..., description="The model to get from")
    id: Any = Field(..., description="The primary key value")
    select: list[str] | None = Field(
        default=None, description="Fields to select"
    )
    include: list[dict[str, Any]] | None = Field(
        default=None, description="Relations to include"
    )


class GetTool(Tool[GetInput, GetResult]):
    """
    Tool to get a single record by primary key.
    """

    name = "db.get"
    description = "Get a single record by its primary key."
    input_schema = GetInput

    def __init__(self, adapter: OrmAdapter, policy: Policy, schema: SchemaMetadata) -> None:
        self.adapter = adapter
        self.policy = policy
        self.schema = schema

    async def execute(
        self,
        input: GetInput,
        ctx: RunContext,
    ) -> GetResult:
        """Execute the get operation."""
        request = GetRequest(
            model=input.model,
            id=input.id,
            select=input.select,
            include=[IncludeClause.model_validate(i) for i in input.include] if input.include else None,
        )

        compiled = self.adapter.compile_get(request, ctx, self.policy, self.schema)
        return await self.adapter.execute_get(compiled, ctx)


# === Aggregate Tool ===


class AggregateInput(BaseModel):
    """Input for aggregate tool."""

    model: str = Field(..., description="The model to aggregate")
    operation: str = Field(..., description="Aggregation: count, sum, avg, min, max")
    field: str | None = Field(
        default=None, description="Field to aggregate (required for sum/avg/min/max)"
    )
    where: list[dict[str, Any]] | None = Field(
        default=None, description="Filter conditions"
    )


class AggregateTool(Tool[AggregateInput, AggregateResult]):
    """
    Tool to perform aggregations on database records.
    """

    name = "db.aggregate"
    description = "Perform aggregations (count, sum, avg, min, max) on records."
    input_schema = AggregateInput

    def __init__(self, adapter: OrmAdapter, policy: Policy, schema: SchemaMetadata) -> None:
        self.adapter = adapter
        self.policy = policy
        self.schema = schema

    async def execute(
        self,
        input: AggregateInput,
        ctx: RunContext,
    ) -> AggregateResult:
        """Execute the aggregation operation."""
        request = AggregateRequest(
            model=input.model,
            operation=input.operation,
            field=input.field,
            where=[FilterClause.model_validate(f) for f in input.where] if input.where else None,
        )

        compiled = self.adapter.compile_aggregate(request, ctx, self.policy, self.schema)
        return await self.adapter.execute_aggregate(compiled, ctx)


# =============================================================================
# MUTATION TOOLS (Phase 2)
# =============================================================================


class CreateInput(BaseModel):
    """Input for create tool."""

    model: str = Field(..., description="The model to create a record in")
    data: dict[str, Any] = Field(..., description="Field values for the new record")
    reason: str | None = Field(
        default=None,
        description="Reason for the mutation (may be required by policy)",
    )
    return_fields: list[str] | None = Field(
        default=None,
        description="Fields to return after creation",
    )


class CreateTool(Tool[CreateInput, CreateResult]):
    """
    Tool to create a new database record.

    Requires write permissions and validates against write policies.
    """

    name = "db.create"
    description = "Create a new database record."
    input_schema = CreateInput

    def __init__(self, adapter: OrmAdapter, policy: Policy, schema: SchemaMetadata) -> None:
        self.adapter = adapter
        self.policy = policy
        self.schema = schema

    async def execute(
        self,
        input: CreateInput,
        ctx: RunContext,
    ) -> CreateResult:
        """Execute the create operation."""
        # Build the request
        request = CreateRequest(
            model=input.model,
            data=input.data,
            reason=input.reason,
            return_fields=input.return_fields,
        )

        # Compile and execute
        compiled = self.adapter.compile_create(request, ctx, self.policy, self.schema)
        return await self.adapter.execute_create(compiled, ctx)


class UpdateInput(BaseModel):
    """Input for update tool."""

    model: str = Field(..., description="The model to update")
    id: Any = Field(..., description="The primary key of the record to update")
    data: dict[str, Any] = Field(..., description="Fields to update")
    reason: str | None = Field(
        default=None,
        description="Reason for the mutation",
    )
    return_fields: list[str] | None = Field(
        default=None,
        description="Fields to return after update",
    )


class UpdateTool(Tool[UpdateInput, UpdateResult]):
    """
    Tool to update a database record by primary key.

    Requires write permissions and validates against write policies.
    """

    name = "db.update"
    description = "Update a database record by its primary key."
    input_schema = UpdateInput

    def __init__(self, adapter: OrmAdapter, policy: Policy, schema: SchemaMetadata) -> None:
        self.adapter = adapter
        self.policy = policy
        self.schema = schema

    async def execute(
        self,
        input: UpdateInput,
        ctx: RunContext,
    ) -> UpdateResult:
        """Execute the update operation."""
        request = UpdateRequest(
            model=input.model,
            id=input.id,
            data=input.data,
            reason=input.reason,
            return_fields=input.return_fields,
        )

        compiled = self.adapter.compile_update(request, ctx, self.policy, self.schema)
        return await self.adapter.execute_update(compiled, ctx)


class DeleteInput(BaseModel):
    """Input for delete tool."""

    model: str = Field(..., description="The model to delete from")
    id: Any = Field(..., description="The primary key of the record to delete")
    reason: str | None = Field(
        default=None,
        description="Reason for the deletion",
    )
    hard: bool = Field(
        default=False,
        description="If True, perform hard delete instead of soft delete",
    )


class DeleteTool(Tool[DeleteInput, DeleteResult]):
    """
    Tool to delete a database record by primary key.

    By default, performs a soft delete if the model supports it.
    Requires write/delete permissions.
    """

    name = "db.delete"
    description = "Delete a database record by its primary key."
    input_schema = DeleteInput

    def __init__(self, adapter: OrmAdapter, policy: Policy, schema: SchemaMetadata) -> None:
        self.adapter = adapter
        self.policy = policy
        self.schema = schema

    async def execute(
        self,
        input: DeleteInput,
        ctx: RunContext,
    ) -> DeleteResult:
        """Execute the delete operation."""
        request = DeleteRequest(
            model=input.model,
            id=input.id,
            reason=input.reason,
            hard=input.hard,
        )

        compiled = self.adapter.compile_delete(request, ctx, self.policy, self.schema)
        return await self.adapter.execute_delete(compiled, ctx)


class BulkUpdateInput(BaseModel):
    """Input for bulk update tool."""

    model: str = Field(..., description="The model to update")
    ids: list[Any] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Primary keys of records to update",
    )
    data: dict[str, Any] = Field(..., description="Fields to update on all records")
    reason: str | None = Field(
        default=None,
        description="Reason for the mutation",
    )


class BulkUpdateTool(Tool[BulkUpdateInput, BulkUpdateResult]):
    """
    Tool to update multiple database records by their primary keys.

    Safer than filter-based bulk updates because it requires explicit IDs.
    Requires write permissions and bulk operation permissions.
    """

    name = "db.bulk_update"
    description = "Update multiple database records by their primary keys."
    input_schema = BulkUpdateInput

    def __init__(self, adapter: OrmAdapter, policy: Policy, schema: SchemaMetadata) -> None:
        self.adapter = adapter
        self.policy = policy
        self.schema = schema

    async def execute(
        self,
        input: BulkUpdateInput,
        ctx: RunContext,
    ) -> BulkUpdateResult:
        """Execute the bulk update operation."""
        request = BulkUpdateRequest(
            model=input.model,
            ids=input.ids,
            data=input.data,
            reason=input.reason,
        )

        compiled = self.adapter.compile_bulk_update(request, ctx, self.policy, self.schema)
        return await self.adapter.execute_bulk_update(compiled, ctx)
