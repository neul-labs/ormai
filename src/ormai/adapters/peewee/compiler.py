"""
Peewee query compiler.

Compiles OrmAI DSL queries into Peewee SelectQuery operations.
"""

from __future__ import annotations

from typing import Any

from peewee import fn

from ormai.adapters.base import CompiledQuery
from ormai.core.context import RunContext
from ormai.core.dsl import (
    AggregateRequest,
    FilterClause,
    FilterOp,
    GetRequest,
    IncludeClause,
    OrderDirection,
    QueryRequest,
)
from ormai.core.types import SchemaMetadata
from ormai.policy.engine import PolicyEngine
from ormai.policy.models import Policy


class PeeweeCompiler:
    """
    Compiles OrmAI DSL queries into Peewee SelectQuery operations.
    """

    def __init__(
        self,
        model_map: dict[str, type],
        policy: Policy,
        schema: SchemaMetadata,
    ) -> None:
        """
        Initialize the compiler.

        Args:
            model_map: Mapping of model names to Peewee model classes
            policy: The policy to apply
            schema: Schema metadata
        """
        self.model_map = model_map
        self.policy = policy
        self.schema = schema
        self.policy_engine = PolicyEngine(policy, schema)

    def compile_query(
        self,
        request: QueryRequest,
        ctx: RunContext,
    ) -> CompiledQuery:
        """
        Compile a query request into a Peewee SelectQuery.
        """
        # Validate against policy and get decisions
        decision = self.policy_engine.validate_query(request, ctx)

        # Get the model class
        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Build the query
        query = model_class.select()

        # Apply filters (user filters + injected scope filters)
        all_filters = list(decision.injected_filters)
        if request.where:
            all_filters.extend(request.where)
        query = self._apply_filters(query, model_class, all_filters)

        # Apply ordering
        if request.order_by:
            query = self._apply_ordering(query, model_class, request.order_by)

        # Apply pagination
        if request.cursor:
            offset = self._decode_cursor(request.cursor)
            query = query.offset(offset)
        query = query.limit(request.take)

        # Note: Peewee handles prefetching differently
        # We'll store includes for post-processing
        includes = request.include or []

        return CompiledQuery(
            query={"select": query, "includes": includes, "model": model_class},
            request=request,
            select_fields=decision.allowed_fields,
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
            timeout_ms=decision.budget.statement_timeout_ms if decision.budget else None,
        )

    def compile_get(
        self,
        request: GetRequest,
        ctx: RunContext,
    ) -> CompiledQuery:
        """
        Compile a get-by-id request into a Peewee SelectQuery.
        """
        # Validate against policy
        decision = self.policy_engine.validate_get(request, ctx)

        # Get the model class
        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Get primary key field
        pk_field = self._get_primary_key_field(model_class)

        # Build the query
        query = model_class.select()

        # Apply primary key filter
        pk_filter = FilterClause(field=pk_field, op=FilterOp.EQ, value=request.id)
        all_filters = [pk_filter] + decision.injected_filters
        query = self._apply_filters(query, model_class, all_filters)

        # Limit to 1
        query = query.limit(1)

        includes = request.include or []

        return CompiledQuery(
            query={"select": query, "includes": includes, "model": model_class},
            request=request,
            select_fields=decision.allowed_fields,
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
            timeout_ms=decision.budget.statement_timeout_ms if decision.budget else None,
        )

    def compile_aggregate(
        self,
        request: AggregateRequest,
        ctx: RunContext,
    ) -> CompiledQuery:
        """
        Compile an aggregation request.
        """
        # Validate against policy
        decision = self.policy_engine.validate_aggregate(request, ctx)

        # Get the model class
        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Build base query with filters
        all_filters = list(decision.injected_filters)
        if request.where:
            all_filters.extend(request.where)

        # Build the aggregation query
        agg_expr = self._build_aggregate_expr(model_class, request.operation, request.field)
        query = model_class.select(agg_expr)

        if all_filters:
            query = self._apply_filters(query, model_class, all_filters)

        return CompiledQuery(
            query={"aggregate": query, "operation": request.operation, "field": request.field},
            request=request,
            select_fields=[],
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
            timeout_ms=decision.budget.statement_timeout_ms if decision.budget else None,
        )

    def _apply_filters(
        self,
        query: Any,
        model_class: type,
        filters: list[FilterClause],
    ) -> Any:
        """Apply filter clauses to a query."""
        for f in filters:
            condition = self._build_filter_condition(model_class, f)
            if condition is not None:
                query = query.where(condition)
        return query

    def _build_filter_condition(
        self,
        model_class: type,
        f: FilterClause,
    ) -> Any:
        """Build a Peewee filter condition from a FilterClause."""
        column = getattr(model_class, f.field, None)
        if column is None:
            return None

        op_str = f.op.value if isinstance(f.op, FilterOp) else f.op

        match op_str:
            case "eq":
                return column == f.value
            case "ne":
                return column != f.value
            case "lt":
                return column < f.value
            case "lte":
                return column <= f.value
            case "gt":
                return column > f.value
            case "gte":
                return column >= f.value
            case "in":
                return column.in_(f.value)
            case "not_in":
                return column.not_in(f.value)
            case "is_null":
                return column.is_null(f.value)
            case "contains":
                return column.contains(f.value)
            case "startswith":
                return column.startswith(f.value)
            case "endswith":
                return column.endswith(f.value)
            case _:
                return None

    def _apply_ordering(
        self,
        query: Any,
        model_class: type,
        order_by: list,
    ) -> Any:
        """Apply ORDER BY clauses to a query."""
        for order in order_by:
            column = getattr(model_class, order.field, None)
            if column is None:
                continue

            if order.direction == OrderDirection.DESC:
                query = query.order_by(column.desc())
            else:
                query = query.order_by(column.asc())

        return query

    def _build_aggregate_expr(
        self,
        model_class: type,
        operation: str,
        field: str | None,
    ) -> Any:
        """Build an aggregation expression."""
        match operation:
            case "count":
                if field:
                    column = getattr(model_class, field)
                    return fn.COUNT(column)
                return fn.COUNT(model_class._meta.primary_key)
            case "sum":
                column = getattr(model_class, field)
                return fn.SUM(column)
            case "avg":
                column = getattr(model_class, field)
                return fn.AVG(column)
            case "min":
                column = getattr(model_class, field)
                return fn.MIN(column)
            case "max":
                column = getattr(model_class, field)
                return fn.MAX(column)
            case _:
                raise ValueError(f"Unsupported aggregation: {operation}")

    def _get_primary_key_field(self, model_class: type) -> str:
        """Get the primary key field name for a model."""
        return model_class._meta.primary_key.name

    def _decode_cursor(self, cursor: str) -> int:
        """Decode a pagination cursor to an offset."""
        try:
            return int(cursor)
        except ValueError:
            return 0

    @staticmethod
    def encode_cursor(offset: int) -> str:
        """Encode an offset as a pagination cursor."""
        return str(offset)
