"""
Tortoise ORM adapter implementation.

The main adapter class that implements the OrmAdapter interface for Tortoise ORM.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from tortoise.functions import Avg, Count, Max, Min, Sum
from tortoise.transactions import in_transaction

from ormai.adapters.base import CompiledQuery, OrmAdapter
from ormai.adapters.tortoise.compiler import TortoiseCompiler
from ormai.adapters.tortoise.introspection import TortoiseIntrospector
from ormai.adapters.tortoise.mutations import MutationExecutor
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
    GetRequest,
    GetResult,
    QueryRequest,
    QueryResult,
    UpdateRequest,
    UpdateResult,
)
from ormai.core.types import SchemaMetadata
from ormai.policy.models import Policy
from ormai.policy.redaction import Redactor

T = TypeVar("T")


class TortoiseAdapter(OrmAdapter):
    """
    Tortoise ORM adapter for OrmAI.

    Provides async database access through Tortoise ORM.
    """

    def __init__(
        self,
        models: list[type],
        policy: Policy,
        connection_name: str = "default",
    ) -> None:
        """
        Initialize the Tortoise adapter.

        Args:
            models: List of Tortoise model classes to expose
            policy: Policy configuration
            connection_name: Tortoise connection name to use
        """
        self.models = models
        self.policy = policy
        self.connection_name = connection_name

        # Initialize components
        self.introspector = TortoiseIntrospector(models)

        # Cache schema on init
        self._schema: SchemaMetadata | None = None
        self._compiler: TortoiseCompiler | None = None
        self._mutation_executor: MutationExecutor | None = None

    @property
    def schema(self) -> SchemaMetadata:
        """Get cached schema, introspecting if needed."""
        if self._schema is None:
            self._schema = self.introspector.introspect()
        return self._schema

    @property
    def compiler(self) -> TortoiseCompiler:
        """Get the query compiler."""
        if self._compiler is None:
            model_map = {m.__name__: m for m in self.models}
            self._compiler = TortoiseCompiler(model_map, self.policy, self.schema)
        return self._compiler

    @property
    def mutation_executor(self) -> MutationExecutor:
        """Get the mutation executor."""
        if self._mutation_executor is None:
            self._mutation_executor = MutationExecutor(self)
        return self._mutation_executor

    async def introspect(self) -> SchemaMetadata:
        """Introspect the database schema."""
        return self.schema

    def compile_query(
        self,
        request: QueryRequest,
        ctx: RunContext,
        policy: Policy,  # noqa: ARG002
        schema: SchemaMetadata,  # noqa: ARG002
    ) -> CompiledQuery:
        """Compile a query request."""
        return self.compiler.compile_query(request, ctx)

    def compile_get(
        self,
        request: GetRequest,
        ctx: RunContext,
        policy: Policy,  # noqa: ARG002
        schema: SchemaMetadata,  # noqa: ARG002
    ) -> CompiledQuery:
        """Compile a get request."""
        return self.compiler.compile_get(request, ctx)

    def compile_aggregate(
        self,
        request: AggregateRequest,
        ctx: RunContext,
        policy: Policy,  # noqa: ARG002
        schema: SchemaMetadata,  # noqa: ARG002
    ) -> CompiledQuery:
        """Compile an aggregate request."""
        return self.compiler.compile_aggregate(request, ctx)

    async def execute_query(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,  # noqa: ARG002
    ) -> QueryResult:
        """Execute a compiled query."""
        queryset = compiled.query
        rows = await queryset

        # Convert to dicts and apply redaction
        request = compiled.request
        if not isinstance(request, QueryRequest):
            raise ValueError("Expected QueryRequest")

        data = self._rows_to_dicts(rows, compiled.select_fields, request.model)

        # Build pagination info
        has_more = len(data) >= request.take
        next_cursor = None
        if has_more:
            current_offset = self._get_current_offset(request.cursor)
            next_cursor = TortoiseCompiler.encode_cursor(current_offset + request.take)

        return QueryResult(
            data=data,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def execute_get(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,  # noqa: ARG002
    ) -> GetResult:
        """Execute a get request."""
        queryset = compiled.query
        row = await queryset.first()

        if row is None:
            return GetResult(data=None, found=False)

        request = compiled.request
        if not isinstance(request, GetRequest):
            raise ValueError("Expected GetRequest")

        data = self._row_to_dict(row, compiled.select_fields, request.model)
        return GetResult(data=data, found=True)

    async def execute_aggregate(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,  # noqa: ARG002
    ) -> AggregateResult:
        """Execute an aggregation."""
        agg_info = compiled.query
        queryset = agg_info["queryset"]
        operation = agg_info["operation"]
        field = agg_info["field"]

        request = compiled.request
        if not isinstance(request, AggregateRequest):
            raise ValueError("Expected AggregateRequest")

        # Execute the aggregation
        value = await self._execute_aggregation(queryset, operation, field)

        return AggregateResult(
            value=value,
            operation=operation,
            field=field,
        )

    async def _execute_aggregation(
        self,
        queryset: Any,
        operation: str,
        field: str | None,
    ) -> Any:
        """Execute a specific aggregation operation."""
        match operation:
            case "count":
                if field:
                    result = await queryset.annotate(val=Count(field)).values("val")
                    return result[0]["val"] if result else 0
                return await queryset.count()
            case "sum":
                result = await queryset.annotate(val=Sum(field)).values("val")
                return result[0]["val"] if result else 0
            case "avg":
                result = await queryset.annotate(val=Avg(field)).values("val")
                return result[0]["val"] if result else None
            case "min":
                result = await queryset.annotate(val=Min(field)).values("val")
                return result[0]["val"] if result else None
            case "max":
                result = await queryset.annotate(val=Max(field)).values("val")
                return result[0]["val"] if result else None
            case _:
                raise ValueError(f"Unsupported aggregation: {operation}")

    async def transaction(
        self,
        ctx: RunContext,  # noqa: ARG002
        fn: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a function within a transaction."""
        async with in_transaction(self.connection_name):
            return await fn(*args, **kwargs)

    def _rows_to_dicts(
        self,
        rows: list[Any],
        fields: list[str],
        model_name: str,
    ) -> list[dict[str, Any]]:
        """Convert ORM rows to dicts with redaction."""
        model_policy = self.policy.get_model_policy(model_name)
        redactor = Redactor(model_policy) if model_policy else None

        result = []
        for row in rows:
            row_dict = self._row_to_dict(row, fields, model_name, redactor)
            result.append(row_dict)
        return result

    def _row_to_dict(
        self,
        row: Any,
        fields: list[str],
        model_name: str,
        redactor: Redactor | None = None,
    ) -> dict[str, Any]:
        """Convert a single ORM row to dict with redaction."""
        # Extract only allowed fields
        data = {}
        for field in fields:
            value = getattr(row, field, None)
            # Handle datetime serialization
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            data[field] = value

        # Apply redaction if we have a policy
        if redactor is None:
            model_policy = self.policy.get_model_policy(model_name)
            if model_policy:
                redactor = Redactor(model_policy)

        if redactor:
            data = redactor.redact_record(data)

        return data

    def _get_current_offset(self, cursor: str | None) -> int:
        """Get current offset from cursor."""
        if cursor is None:
            return 0
        try:
            return int(cursor)
        except ValueError:
            return 0

    # =========================================================================
    # MUTATION METHODS
    # =========================================================================

    def compile_create(
        self,
        request: CreateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a create request."""
        return self.mutation_executor.compile_create(request, ctx, policy, schema)

    def compile_update(
        self,
        request: UpdateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile an update request."""
        return self.mutation_executor.compile_update(request, ctx, policy, schema)

    def compile_delete(
        self,
        request: DeleteRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a delete request."""
        return self.mutation_executor.compile_delete(request, ctx, policy, schema)

    def compile_bulk_update(
        self,
        request: BulkUpdateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a bulk update request."""
        return self.mutation_executor.compile_bulk_update(request, ctx, policy, schema)

    async def execute_create(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> CreateResult:
        """Execute a create request."""
        return await self.mutation_executor.execute_create(compiled, ctx)

    async def execute_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> UpdateResult:
        """Execute an update request."""
        return await self.mutation_executor.execute_update(compiled, ctx)

    async def execute_delete(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> DeleteResult:
        """Execute a delete request."""
        return await self.mutation_executor.execute_delete(compiled, ctx)

    async def execute_bulk_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> BulkUpdateResult:
        """Execute a bulk update request."""
        return await self.mutation_executor.execute_bulk_update(compiled, ctx)
