"""
Peewee adapter implementation.

The main adapter class that implements the OrmAdapter interface for Peewee.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from peewee import Database, prefetch

from ormai.adapters.base import CompiledQuery, OrmAdapter
from ormai.adapters.peewee.compiler import PeeweeCompiler
from ormai.adapters.peewee.introspection import PeeweeIntrospector
from ormai.core.context import RunContext
from ormai.core.dsl import (
    AggregateRequest,
    AggregateResult,
    GetRequest,
    GetResult,
    QueryRequest,
    QueryResult,
)
from ormai.core.types import SchemaMetadata
from ormai.policy.models import Policy
from ormai.policy.redaction import Redactor

T = TypeVar("T")


class PeeweeAdapter(OrmAdapter):
    """
    Peewee adapter for OrmAI.

    Provides synchronous database access through Peewee.
    Note: Async methods run sync operations in a thread pool.
    """

    def __init__(
        self,
        database: Database,
        models: list[type],
        policy: Policy,
    ) -> None:
        """
        Initialize the Peewee adapter.

        Args:
            database: Peewee database instance
            models: List of Peewee model classes to expose
            policy: Policy configuration
        """
        self.database = database
        self.models = models
        self.policy = policy

        # Initialize components
        self.introspector = PeeweeIntrospector(models)

        # Cache schema on init
        self._schema: SchemaMetadata | None = None
        self._compiler: PeeweeCompiler | None = None

    @property
    def schema(self) -> SchemaMetadata:
        """Get cached schema, introspecting if needed."""
        if self._schema is None:
            self._schema = self.introspector.introspect()
        return self._schema

    @property
    def compiler(self) -> PeeweeCompiler:
        """Get the query compiler."""
        if self._compiler is None:
            model_map = {m.__name__: m for m in self.models}
            self._compiler = PeeweeCompiler(model_map, self.policy, self.schema)
        return self._compiler

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
        # Run sync operation in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._execute_query_sync, compiled, ctx
        )

    def _execute_query_sync(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,  # noqa: ARG002
    ) -> QueryResult:
        """Execute query synchronously."""
        query_info = compiled.query
        query = query_info["select"]
        includes = query_info["includes"]
        model_class = query_info["model"]

        # Execute the query
        with self.database.connection_context():
            rows = list(query)

            # Handle prefetching for includes
            if includes and rows:
                rows = self._apply_prefetch(rows, model_class, includes)

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
            next_cursor = PeeweeCompiler.encode_cursor(current_offset + request.take)

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
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._execute_get_sync, compiled, ctx
        )

    def _execute_get_sync(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,  # noqa: ARG002
    ) -> GetResult:
        """Execute get synchronously."""
        query_info = compiled.query
        query = query_info["select"]

        with self.database.connection_context():
            row = query.first()

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
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._execute_aggregate_sync, compiled, ctx
        )

    def _execute_aggregate_sync(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,  # noqa: ARG002
    ) -> AggregateResult:
        """Execute aggregation synchronously."""
        agg_info = compiled.query
        query = agg_info["aggregate"]
        operation = agg_info["operation"]
        field = agg_info["field"]

        request = compiled.request
        if not isinstance(request, AggregateRequest):
            raise ValueError("Expected AggregateRequest")

        with self.database.connection_context():
            result = query.scalar()

        return AggregateResult(
            value=result,
            operation=operation,
            field=field,
        )

    async def transaction(
        self,
        ctx: RunContext,  # noqa: ARG002
        fn: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a function within a transaction."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._run_in_transaction,
            fn,
            args,
            kwargs,
        )

    def _run_in_transaction(
        self,
        fn: Callable[..., T],
        args: tuple,
        kwargs: dict,
    ) -> T:
        """Run function in transaction synchronously."""
        with self.database.atomic():
            return fn(*args, **kwargs)

    def _apply_prefetch(
        self,
        rows: list[Any],
        model_class: type,
        includes: list,
    ) -> list[Any]:
        """Apply prefetching for related models."""
        if not includes:
            return rows

        # Build prefetch queries for each include
        prefetch_queries = []
        for include in includes:
            rel_name = include.relation
            rel_field = getattr(model_class, rel_name, None)
            if rel_field is not None:
                # Get the related model
                rel_model = rel_field.rel_model
                prefetch_queries.append(rel_model.select())

        if prefetch_queries:
            return list(prefetch(rows, *prefetch_queries))
        return rows

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
