"""
SQLAlchemy adapter implementation.

The main adapter class that implements the OrmAdapter interface for SQLAlchemy.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

from ormai.adapters.base import CompiledQuery, OrmAdapter
from ormai.adapters.sqlalchemy.compiler import SQLAlchemyCompiler
from ormai.adapters.sqlalchemy.introspection import SQLAlchemyIntrospector
from ormai.adapters.sqlalchemy.session import SessionManager
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

    async def execute_query(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> QueryResult:
        """Execute a compiled query."""
        if self.is_async:
            return await self._execute_query_async(compiled, ctx)
        else:
            return self._execute_query_sync(compiled, ctx)

    def _execute_query_sync(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> QueryResult:
        """Execute query synchronously."""
        session: Session = ctx.db
        result = session.execute(compiled.query)
        rows = result.scalars().all()

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
            next_cursor = SQLAlchemyCompiler.encode_cursor(current_offset + request.take)

        return QueryResult(
            data=data,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def _execute_query_async(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> QueryResult:
        """Execute query asynchronously."""
        session: AsyncSession = ctx.db
        result = await session.execute(compiled.query)
        rows = result.scalars().all()

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
            next_cursor = SQLAlchemyCompiler.encode_cursor(current_offset + request.take)

        return QueryResult(
            data=data,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def execute_get(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> GetResult:
        """Execute a get request."""
        if self.is_async:
            return await self._execute_get_async(compiled, ctx)
        else:
            return self._execute_get_sync(compiled, ctx)

    def _execute_get_sync(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> GetResult:
        """Execute get synchronously."""
        session: Session = ctx.db
        result = session.execute(compiled.query)
        row = result.scalars().first()

        if row is None:
            return GetResult(data=None, found=False)

        request = compiled.request
        if not isinstance(request, GetRequest):
            raise ValueError("Expected GetRequest")

        data = self._row_to_dict(row, compiled.select_fields, request.model)
        return GetResult(data=data, found=True)

    async def _execute_get_async(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> GetResult:
        """Execute get asynchronously."""
        session: AsyncSession = ctx.db
        result = await session.execute(compiled.query)
        row = result.scalars().first()

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
        ctx: RunContext,
    ) -> AggregateResult:
        """Execute an aggregation."""
        if self.is_async:
            return await self._execute_aggregate_async(compiled, ctx)
        else:
            return self._execute_aggregate_sync(compiled, ctx)

    def _execute_aggregate_sync(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> AggregateResult:
        """Execute aggregation synchronously."""
        session: Session = ctx.db
        result = session.execute(compiled.query)
        value = result.scalar()

        request = compiled.request
        if not isinstance(request, AggregateRequest):
            raise ValueError("Expected AggregateRequest")

        return AggregateResult(
            value=value,
            operation=request.operation,
            field=request.field,
        )

    async def _execute_aggregate_async(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> AggregateResult:
        """Execute aggregation asynchronously."""
        session: AsyncSession = ctx.db
        result = await session.execute(compiled.query)
        value = result.scalar()

        request = compiled.request
        if not isinstance(request, AggregateRequest):
            raise ValueError("Expected AggregateRequest")

        return AggregateResult(
            value=value,
            operation=request.operation,
            field=request.field,
        )

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
