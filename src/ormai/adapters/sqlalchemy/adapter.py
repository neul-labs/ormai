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

    # =========================================================================
    # MUTATION METHODS (Phase 2)
    # =========================================================================

    def compile_create(
        self,
        request: CreateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a create request."""
        decision = self.compiler.policy_engine.validate_create(request, ctx)

        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Prepare data with injected scope values
        data = dict(request.data)
        row_policy = policy.get_row_policy(request.model)
        if row_policy.tenant_scope_field and ctx.principal.tenant_id:
            data[row_policy.tenant_scope_field] = ctx.principal.tenant_id

        return CompiledQuery(
            query={"model_class": model_class, "data": data, "operation": "create"},
            request=request,
            select_fields=decision.allowed_fields,
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
        )

    def compile_update(
        self,
        request: UpdateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile an update request."""
        decision = self.compiler.policy_engine.validate_update(request, ctx)

        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        pk_column = self.compiler._get_primary_key_column(model_class)

        return CompiledQuery(
            query={
                "model_class": model_class,
                "pk_column": pk_column,
                "pk_value": request.id,
                "data": request.data,
                "operation": "update",
            },
            request=request,
            select_fields=decision.allowed_fields,
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
        )

    def compile_delete(
        self,
        request: DeleteRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a delete request."""
        decision = self.compiler.policy_engine.validate_delete(request, ctx)

        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        pk_column = self.compiler._get_primary_key_column(model_class)

        # Determine soft delete field
        row_policy = policy.get_row_policy(request.model)
        soft_delete_field = row_policy.soft_delete_field if not request.hard else None

        return CompiledQuery(
            query={
                "model_class": model_class,
                "pk_column": pk_column,
                "pk_value": request.id,
                "soft_delete_field": soft_delete_field,
                "operation": "delete",
            },
            request=request,
            select_fields=[],
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
        )

    def compile_bulk_update(
        self,
        request: BulkUpdateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a bulk update request."""
        decision = self.compiler.policy_engine.validate_bulk_update(request, ctx)

        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        pk_column = self.compiler._get_primary_key_column(model_class)

        return CompiledQuery(
            query={
                "model_class": model_class,
                "pk_column": pk_column,
                "pk_values": request.ids,
                "data": request.data,
                "operation": "bulk_update",
            },
            request=request,
            select_fields=[],
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
        )

    async def execute_create(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> CreateResult:
        """Execute a create request."""
        if self.is_async:
            return await self._execute_create_async(compiled, ctx)
        else:
            return self._execute_create_sync(compiled, ctx)

    def _execute_create_sync(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> CreateResult:
        """Execute create synchronously."""
        session: Session = ctx.db
        query_info = compiled.query
        model_class = query_info["model_class"]
        data = query_info["data"]

        # Create the instance
        instance = model_class(**data)
        session.add(instance)
        session.flush()  # To get the ID

        # Get the primary key value
        pk_column = self.compiler._get_primary_key_column(model_class)
        pk_value = getattr(instance, pk_column)

        # Convert to dict
        request = compiled.request
        if not isinstance(request, CreateRequest):
            raise ValueError("Expected CreateRequest")

        result_data = self._row_to_dict(instance, compiled.select_fields, request.model)

        return CreateResult(
            data=result_data,
            id=pk_value,
            success=True,
        )

    async def _execute_create_async(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> CreateResult:
        """Execute create asynchronously."""
        session: AsyncSession = ctx.db
        query_info = compiled.query
        model_class = query_info["model_class"]
        data = query_info["data"]

        # Create the instance
        instance = model_class(**data)
        session.add(instance)
        await session.flush()

        # Get the primary key value
        pk_column = self.compiler._get_primary_key_column(model_class)
        pk_value = getattr(instance, pk_column)

        # Convert to dict
        request = compiled.request
        if not isinstance(request, CreateRequest):
            raise ValueError("Expected CreateRequest")

        result_data = self._row_to_dict(instance, compiled.select_fields, request.model)

        return CreateResult(
            data=result_data,
            id=pk_value,
            success=True,
        )

    async def execute_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> UpdateResult:
        """Execute an update request."""
        if self.is_async:
            return await self._execute_update_async(compiled, ctx)
        else:
            return self._execute_update_sync(compiled, ctx)

    def _execute_update_sync(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> UpdateResult:
        """Execute update synchronously."""
        from sqlalchemy import update

        session: Session = ctx.db
        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_value = query_info["pk_value"]
        data = query_info["data"]

        # Build update statement
        pk_attr = getattr(model_class, pk_column)
        stmt = update(model_class).where(pk_attr == pk_value).values(**data)

        # Apply scope filters
        for f in compiled.injected_filters:
            column = getattr(model_class, f.field, None)
            if column is not None:
                stmt = stmt.where(column == f.value)

        result = session.execute(stmt)
        session.flush()

        if result.rowcount == 0:
            return UpdateResult(data=None, success=True, found=False)

        # Fetch the updated row
        request = compiled.request
        if not isinstance(request, UpdateRequest):
            raise ValueError("Expected UpdateRequest")

        from sqlalchemy import select
        fetch_stmt = select(model_class).where(pk_attr == pk_value)
        row = session.execute(fetch_stmt).scalars().first()

        if row:
            result_data = self._row_to_dict(row, compiled.select_fields, request.model)
            return UpdateResult(data=result_data, success=True, found=True)

        return UpdateResult(data=None, success=True, found=False)

    async def _execute_update_async(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> UpdateResult:
        """Execute update asynchronously."""
        from sqlalchemy import select, update

        session: AsyncSession = ctx.db
        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_value = query_info["pk_value"]
        data = query_info["data"]

        # Build update statement
        pk_attr = getattr(model_class, pk_column)
        stmt = update(model_class).where(pk_attr == pk_value).values(**data)

        # Apply scope filters
        for f in compiled.injected_filters:
            column = getattr(model_class, f.field, None)
            if column is not None:
                stmt = stmt.where(column == f.value)

        result = await session.execute(stmt)
        await session.flush()

        if result.rowcount == 0:
            return UpdateResult(data=None, success=True, found=False)

        # Fetch the updated row
        request = compiled.request
        if not isinstance(request, UpdateRequest):
            raise ValueError("Expected UpdateRequest")

        fetch_stmt = select(model_class).where(pk_attr == pk_value)
        row_result = await session.execute(fetch_stmt)
        row = row_result.scalars().first()

        if row:
            result_data = self._row_to_dict(row, compiled.select_fields, request.model)
            return UpdateResult(data=result_data, success=True, found=True)

        return UpdateResult(data=None, success=True, found=False)

    async def execute_delete(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> DeleteResult:
        """Execute a delete request."""
        if self.is_async:
            return await self._execute_delete_async(compiled, ctx)
        else:
            return self._execute_delete_sync(compiled, ctx)

    def _execute_delete_sync(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> DeleteResult:
        """Execute delete synchronously."""
        from datetime import datetime

        from sqlalchemy import delete, update

        session: Session = ctx.db
        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_value = query_info["pk_value"]
        soft_delete_field = query_info.get("soft_delete_field")

        pk_attr = getattr(model_class, pk_column)

        if soft_delete_field:
            # Soft delete - set the soft delete field to current timestamp
            stmt = update(model_class).where(pk_attr == pk_value).values(
                **{soft_delete_field: datetime.utcnow()}
            )
        else:
            # Hard delete
            stmt = delete(model_class).where(pk_attr == pk_value)

        # Apply scope filters
        for f in compiled.injected_filters:
            column = getattr(model_class, f.field, None)
            if column is not None:
                stmt = stmt.where(column == f.value)

        result = session.execute(stmt)
        session.flush()

        return DeleteResult(
            success=True,
            found=result.rowcount > 0,
            soft_deleted=soft_delete_field is not None,
        )

    async def _execute_delete_async(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> DeleteResult:
        """Execute delete asynchronously."""
        from datetime import datetime

        from sqlalchemy import delete, update

        session: AsyncSession = ctx.db
        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_value = query_info["pk_value"]
        soft_delete_field = query_info.get("soft_delete_field")

        pk_attr = getattr(model_class, pk_column)

        if soft_delete_field:
            stmt = update(model_class).where(pk_attr == pk_value).values(
                **{soft_delete_field: datetime.utcnow()}
            )
        else:
            stmt = delete(model_class).where(pk_attr == pk_value)

        # Apply scope filters
        for f in compiled.injected_filters:
            column = getattr(model_class, f.field, None)
            if column is not None:
                stmt = stmt.where(column == f.value)

        result = await session.execute(stmt)
        await session.flush()

        return DeleteResult(
            success=True,
            found=result.rowcount > 0,
            soft_deleted=soft_delete_field is not None,
        )

    async def execute_bulk_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> BulkUpdateResult:
        """Execute a bulk update request."""
        if self.is_async:
            return await self._execute_bulk_update_async(compiled, ctx)
        else:
            return self._execute_bulk_update_sync(compiled, ctx)

    def _execute_bulk_update_sync(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> BulkUpdateResult:
        """Execute bulk update synchronously."""
        from sqlalchemy import update

        session: Session = ctx.db
        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_values = query_info["pk_values"]
        data = query_info["data"]

        pk_attr = getattr(model_class, pk_column)
        stmt = update(model_class).where(pk_attr.in_(pk_values)).values(**data)

        # Apply scope filters
        for f in compiled.injected_filters:
            column = getattr(model_class, f.field, None)
            if column is not None:
                stmt = stmt.where(column == f.value)

        result = session.execute(stmt)
        session.flush()

        return BulkUpdateResult(
            updated_count=result.rowcount,
            success=True,
        )

    async def _execute_bulk_update_async(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> BulkUpdateResult:
        """Execute bulk update asynchronously."""
        from sqlalchemy import update

        session: AsyncSession = ctx.db
        query_info = compiled.query
        model_class = query_info["model_class"]
        pk_column = query_info["pk_column"]
        pk_values = query_info["pk_values"]
        data = query_info["data"]

        pk_attr = getattr(model_class, pk_column)
        stmt = update(model_class).where(pk_attr.in_(pk_values)).values(**data)

        # Apply scope filters
        for f in compiled.injected_filters:
            column = getattr(model_class, f.field, None)
            if column is not None:
                stmt = stmt.where(column == f.value)

        result = await session.execute(stmt)
        await session.flush()

        return BulkUpdateResult(
            updated_count=result.rowcount,
            success=True,
        )

    @property
    def model_map(self) -> dict[str, type]:
        """Get the model name to class mapping."""
        return {m.__name__: m for m in self.models}
