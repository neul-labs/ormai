"""
Query execution methods for SQLAlchemy adapter.

This module contains the query execution logic (query, get, aggregate).
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ormai.adapters.base import CompiledQuery
from ormai.core.dsl import (
    AggregateRequest,
    AggregateResult,
    GetRequest,
    GetResult,
    QueryRequest,
    QueryResult,
)

if TYPE_CHECKING:
    from ormai.adapters.sqlalchemy.adapter import SQLAlchemyAdapter

# Import compiler for cursor encoding
from ormai.adapters.sqlalchemy.compiler import SQLAlchemyCompiler


class QueryExecutor:
    """
    Handles query execution for SQLAlchemy adapter.

    Contains methods for executing queries, gets, and aggregates.
    """

    def __init__(self, adapter: "SQLAlchemyAdapter") -> None:
        """Initialize with reference to parent adapter."""
        self._adapter = adapter

    def execute_query(
        self,
        compiled: CompiledQuery,
        ctx: Any,
    ) -> QueryResult:
        """Execute a query request."""
        if self._adapter.is_async:
            from sqlalchemy.ext.asyncio import AsyncSession

            session: AsyncSession = ctx.db
            return self._execute_query_async(session, compiled)
        else:
            session: Session = ctx.db
            return self._execute_query_sync(session, compiled)

    def _execute_query_sync(
        self,
        session: Session,
        compiled: CompiledQuery,
    ) -> QueryResult:
        """Execute query synchronously."""
        result = session.execute(compiled.query)
        rows = result.scalars().all()
        return self._build_query_result(rows, compiled)

    async def _execute_query_async(
        self,
        session: AsyncSession,
        compiled: CompiledQuery,
    ) -> QueryResult:
        """Execute query asynchronously."""
        result = await session.execute(compiled.query)
        rows = result.scalars().all()
        return self._build_query_result(rows, compiled)

    def _build_query_result(
        self,
        rows: list[Any],
        compiled: CompiledQuery,
    ) -> QueryResult:
        """Build a QueryResult from rows."""
        request = compiled.request
        if not isinstance(request, QueryRequest):
            raise ValueError("Expected QueryRequest")

        data = self._adapter._rows_to_dicts(
            rows, compiled.select_fields, request.model
        )

        # Build pagination info
        has_more = len(data) >= request.take
        next_cursor = None
        if has_more:
            current_offset = self._adapter._get_current_offset(request.cursor)
            next_cursor = SQLAlchemyCompiler.encode_cursor(
                current_offset + request.take
            )

        return QueryResult(
            data=data,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def execute_get(
        self,
        compiled: CompiledQuery,
        ctx: Any,
    ) -> GetResult:
        """Execute a get-by-id request."""
        if self._adapter.is_async:
            from sqlalchemy.ext.asyncio import AsyncSession

            session: AsyncSession = ctx.db
            return self._execute_get_async(session, compiled)
        else:
            session: Session = ctx.db
            return self._execute_get_sync(session, compiled)

    def _execute_get_sync(
        self,
        session: Session,
        compiled: CompiledQuery,
    ) -> GetResult:
        """Execute get synchronously."""
        result = session.execute(compiled.query)
        row = result.scalars().first()
        return self._build_get_result(row, compiled)

    async def _execute_get_async(
        self,
        session: AsyncSession,
        compiled: CompiledQuery,
    ) -> GetResult:
        """Execute get asynchronously."""
        result = await session.execute(compiled.query)
        row = result.scalars().first()
        return self._build_get_result(row, compiled)

    def _build_get_result(
        self,
        row: Any,
        compiled: CompiledQuery,
    ) -> GetResult:
        """Build a GetResult from a row."""
        if row is None:
            return GetResult(data=None, found=False)

        request = compiled.request
        if not isinstance(request, GetRequest):
            raise ValueError("Expected GetRequest")

        data = self._adapter._row_to_dict(
            row, compiled.select_fields, request.model
        )
        return GetResult(data=data, found=True)

    def execute_aggregate(
        self,
        compiled: CompiledQuery,
        ctx: Any,
    ) -> AggregateResult:
        """Execute an aggregation request."""
        if self._adapter.is_async:
            from sqlalchemy.ext.asyncio import AsyncSession

            session: AsyncSession = ctx.db
            return self._execute_aggregate_async(session, compiled)
        else:
            session: Session = ctx.db
            return self._execute_aggregate_sync(session, compiled)

    def _execute_aggregate_sync(
        self,
        session: Session,
        compiled: CompiledQuery,
    ) -> AggregateResult:
        """Execute aggregation synchronously."""
        from sqlalchemy import func, select

        result = session.execute(compiled.query)
        value = result.scalar()

        count_query = select(func.count()).select_from(compiled.query.subquery())
        count_result = session.execute(count_query)
        row_count = count_result.scalar()

        return self._build_aggregate_result(value, row_count or 0, compiled)

    async def _execute_aggregate_async(
        self,
        session: AsyncSession,
        compiled: CompiledQuery,
    ) -> AggregateResult:
        """Execute aggregation asynchronously."""
        from sqlalchemy import func, select

        result = await session.execute(compiled.query)
        value = result.scalar()

        count_query = select(func.count()).select_from(compiled.query.subquery())
        count_result = await session.execute(count_query)
        row_count = count_result.scalar()

        return self._build_aggregate_result(value, row_count or 0, compiled)

    def _build_aggregate_result(
        self,
        value: Any,
        row_count: int,
        compiled: CompiledQuery,
    ) -> AggregateResult:
        """Build an AggregateResult from computed values."""
        request = compiled.request
        if not isinstance(request, AggregateRequest):
            raise ValueError("Expected AggregateRequest")

        return AggregateResult(
            value=value,
            operation=request.operation,
            field=request.field,
            row_count=row_count,
        )
