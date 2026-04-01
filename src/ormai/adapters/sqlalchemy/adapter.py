"""
SQLAlchemy adapter implementation.

The main adapter class that implements the OrmAdapter interface for SQLAlchemy.
Delegates query and mutation execution to specialized modules.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Session

from ormai.adapters.base import CompiledQuery, OrmAdapter
from ormai.adapters.sqlalchemy.compiler import SQLAlchemyCompiler
from ormai.adapters.sqlalchemy.introspection import SQLAlchemyIntrospector
from ormai.adapters.sqlalchemy.queries import QueryExecutor
from ormai.adapters.sqlalchemy.mutations import MutationExecutor
from ormai.adapters.sqlalchemy.session import SessionManager
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


class SQLAlchemyAdapter(OrmAdapter):
    """
    SQLAlchemy adapter for OrmAI.

    Supports both sync and async SQLAlchemy engines.
    """

    def __init__(
        self,
        engine: Engine | AsyncEngine,
        models: list[type],
        policy: Policy,
        session_manager: SessionManager | None = None,
    ) -> None:
        """
        Initialize the SQLAlchemy adapter.

        Args:
            engine: SQLAlchemy engine (sync or async)
            models: List of SQLAlchemy model classes to expose
            policy: Policy configuration
            session_manager: Optional custom session manager
        """
        self.engine = engine
        self.models = models
        self.policy = policy
        self.is_async = isinstance(engine, AsyncEngine)

        # Initialize components
        self.session_manager = session_manager or SessionManager(engine)
        self.introspector = SQLAlchemyIntrospector(models)

        # Cache schema on init
        self._schema: SchemaMetadata | None = None
        self._compiler: SQLAlchemyCompiler | None = None

        # Cache for Redactor instances per model
        self._redactor_cache: dict[str, Redactor | None] = {}

        # Initialize sub-executors
        self._query_executor = QueryExecutor(self)
        self._mutation_executor = MutationExecutor(self)

    @property
    def schema(self) -> SchemaMetadata:
        """Get cached schema, introspecting if needed."""
        if self._schema is None:
            self._schema = self.introspector.introspect()
        return self._schema

    @property
    def compiler(self) -> SQLAlchemyCompiler:
        """Get the query compiler."""
        if self._compiler is None:
            model_map = {m.__name__: m for m in self.models}
            self._compiler = SQLAlchemyCompiler(model_map, self.policy, self.schema)
        return self._compiler

    async def introspect(self) -> SchemaMetadata:
        """Introspect the database schema."""
        return self.schema

    @property
    def model_map(self) -> dict[str, type]:
        """Get the model name to class mapping."""
        return {m.__name__: m for m in self.models}

    # =========================================================================
    # COMPILATION METHODS (delegated to compiler)
    # =========================================================================

    def compile_query(
        self,
        request: QueryRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a query request."""
        return self.compiler.compile_query(request, ctx)

    def compile_get(
        self,
        request: GetRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a get request."""
        return self.compiler.compile_get(request, ctx)

    def compile_aggregate(
        self,
        request: AggregateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile an aggregate request."""
        return self.compiler.compile_aggregate(request, ctx)

    # =========================================================================
    # QUERY EXECUTION (delegated to QueryExecutor)
    # =========================================================================

    async def execute_query(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> QueryResult:
        """Execute a compiled query."""
        return self._query_executor.execute_query(compiled, ctx)

    async def execute_get(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> GetResult:
        """Execute a get request."""
        return self._query_executor.execute_get(compiled, ctx)

    async def execute_aggregate(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> AggregateResult:
        """Execute an aggregation."""
        return self._query_executor.execute_aggregate(compiled, ctx)

    # =========================================================================
    # MUTATION COMPILATION (delegated to MutationExecutor)
    # =========================================================================

    def compile_create(
        self,
        request: CreateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a create request."""
        return self._mutation_executor.compile_create(request, ctx, policy, schema)

    def compile_update(
        self,
        request: UpdateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile an update request."""
        return self._mutation_executor.compile_update(request, ctx, policy, schema)

    def compile_delete(
        self,
        request: DeleteRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a delete request."""
        return self._mutation_executor.compile_delete(request, ctx, policy, schema)

    def compile_bulk_update(
        self,
        request: BulkUpdateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a bulk update request."""
        return self._mutation_executor.compile_bulk_update(
            request, ctx, policy, schema
        )

    # =========================================================================
    # MUTATION EXECUTION (delegated to MutationExecutor)
    # =========================================================================

    async def execute_create(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> CreateResult:
        """Execute a create request."""
        return self._mutation_executor.execute_create(compiled, ctx)

    async def execute_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> UpdateResult:
        """Execute an update request."""
        return self._mutation_executor.execute_update(compiled, ctx)

    async def execute_delete(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> DeleteResult:
        """Execute a delete request."""
        return self._mutation_executor.execute_delete(compiled, ctx)

    async def execute_bulk_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> BulkUpdateResult:
        """Execute a bulk update request."""
        return self._mutation_executor.execute_bulk_update(compiled, ctx)

    # =========================================================================
    # TRANSACTION SUPPORT
    # =========================================================================

    async def transaction(
        self,
        ctx: RunContext,
        fn: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a function within a transaction."""
        if self.is_async:
            async with self.session_manager.async_session() as session:
                ctx.db = session
                return await fn(*args, **kwargs)
        else:
            with self.session_manager.session() as session:
                ctx.db = session
                return fn(*args, **kwargs)

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_redactor(self, model_name: str) -> Redactor | None:
        """
        Get a cached Redactor instance for the given model.

        Redactors are cached per model to avoid repeated instantiation
        when processing multiple rows from the same model.
        """
        if model_name not in self._redactor_cache:
            model_policy = self.policy.get_model_policy(model_name)
            self._redactor_cache[model_name] = (
                Redactor(model_policy) if model_policy else None
            )
        return self._redactor_cache[model_name]

    def _invalidate_redactor_cache(self, model_name: str | None = None) -> None:
        """
        Invalidate the redactor cache.

        Args:
            model_name: Specific model to invalidate, or None to clear all
        """
        if model_name is None:
            self._redactor_cache.clear()
        elif model_name in self._redactor_cache:
            del self._redactor_cache[model_name]

    def _rows_to_dicts(
        self,
        rows: list[Any],
        fields: list[str],
        model_name: str,
    ) -> list[dict[str, Any]]:
        """Convert ORM rows to dicts with redaction."""
        redactor = self._get_redactor(model_name)
        return [
            self._row_to_dict(row, fields, model_name, redactor) for row in rows
        ]

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

        # Use cached redactor if not provided
        if redactor is None:
            redactor = self._get_redactor(model_name)

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

    def _apply_scope_filters(
        self,
        stmt: Any,
        model_class: type,
        filters: list,
    ) -> Any:
        """Apply scope filters to a statement."""
        for f in filters:
            column = getattr(model_class, f.field, None)
            if column is not None:
                stmt = stmt.where(column == f.value)
        return stmt
