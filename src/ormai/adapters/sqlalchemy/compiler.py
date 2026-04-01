"""
SQLAlchemy query compiler.

Compiles OrmAI DSL queries into SQLAlchemy select statements.
"""

from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import selectinload

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
from ormai.core.errors import ValidationError
from ormai.core.types import DEFAULT_PRIMARY_KEY, SchemaMetadata
from ormai.policy.engine import PolicyEngine
from ormai.policy.models import Policy


class SQLAlchemyCompiler:
    """
    Compiles OrmAI DSL queries into SQLAlchemy statements.
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
            model_map: Mapping of model names to SQLAlchemy model classes
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
        Compile a query request into a SQLAlchemy select statement.
        """
        # Validate against policy and get decisions
        decision = self.policy_engine.validate_query(request, ctx)

        # Get the model class
        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Build the select statement
        stmt = self._build_select(model_class, decision.allowed_fields)

        # Apply filters (user filters + injected scope filters)
        all_filters = list(decision.injected_filters)
        if request.where:
            all_filters.extend(request.where)
        stmt = self._apply_filters(stmt, model_class, all_filters)

        # Apply ordering
        if request.order_by:
            stmt = self._apply_ordering(stmt, model_class, request.order_by)

        # Apply pagination
        stmt = stmt.limit(request.take)
        if request.cursor:
            offset = self._decode_cursor(request.cursor)
            stmt = stmt.offset(offset)

        # Apply includes
        if request.include:
            stmt = self._apply_includes(stmt, model_class, request.include)

        return CompiledQuery(
            query=stmt,
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
        Compile a get-by-id request into a SQLAlchemy select statement.
        """
        # Validate against policy
        decision = self.policy_engine.validate_get(request, ctx)

        # Get the model class
        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Get primary key column
        pk_column = self._get_primary_key_column(model_class)

        # Build the select statement
        stmt = self._build_select(model_class, decision.allowed_fields)

        # Apply primary key filter
        pk_filter = FilterClause(field=pk_column, op=FilterOp.EQ, value=request.id)
        all_filters = [pk_filter] + decision.injected_filters
        stmt = self._apply_filters(stmt, model_class, all_filters)

        # Apply includes
        if request.include:
            stmt = self._apply_includes(stmt, model_class, request.include)

        # Limit to 1
        stmt = stmt.limit(1)

        return CompiledQuery(
            query=stmt,
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
        Compile an aggregation request into a SQLAlchemy select statement.
        """
        # Validate against policy
        decision = self.policy_engine.validate_aggregate(request, ctx)

        # Get the model class
        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Build aggregation expression
        agg_expr = self._build_aggregate_expr(model_class, request.operation, request.field)

        # Build the select statement
        stmt = select(agg_expr)

        # Apply filters
        all_filters = list(decision.injected_filters)
        if request.where:
            all_filters.extend(request.where)

        if all_filters:
            conditions = self._build_filter_conditions(model_class, all_filters)
            stmt = stmt.where(and_(*conditions))

        return CompiledQuery(
            query=stmt,
            request=request,
            select_fields=[],
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
            timeout_ms=decision.budget.statement_timeout_ms if decision.budget else None,
        )

    def _build_select(
        self,
        model_class: type,
        fields: list[str],
    ) -> Select:
        """Build a SELECT statement for the given model and fields."""
        # For now, select the whole model - field filtering happens in result processing
        # This is simpler and works better with relationships
        return select(model_class)

    def _apply_filters(
        self,
        stmt: Select,
        model_class: type,
        filters: list[FilterClause],
    ) -> Select:
        """Apply filter clauses to a statement."""
        if not filters:
            return stmt

        conditions = self._build_filter_conditions(model_class, filters)
        return stmt.where(and_(*conditions))

    def _build_filter_conditions(
        self,
        model_class: type,
        filters: list[FilterClause],
    ) -> list[Any]:
        """Build SQLAlchemy filter conditions from FilterClause list."""
        conditions = []

        for f in filters:
            column = getattr(model_class, f.field, None)
            if column is None:
                raise ValidationError(
                    f"Filter field '{f.field}' does not exist on model '{model_class.__name__}'",
                    field=f.field,
                )

            condition = self._build_single_condition(column, f.op, f.value)
            if condition is not None:
                conditions.append(condition)

        return conditions

    def _build_single_condition(
        self,
        column: Any,
        op: FilterOp | str,
        value: Any,
    ) -> Any:
        """Build a single SQLAlchemy condition."""
        op_str = op.value if isinstance(op, FilterOp) else op

        match op_str:
            case "eq":
                return column == value
            case "ne":
                return column != value
            case "lt":
                return column < value
            case "lte":
                return column <= value
            case "gt":
                return column > value
            case "gte":
                return column >= value
            case "in":
                return column.in_(value)
            case "not_in":
                return column.not_in(value)
            case "is_null":
                return column.is_(None) if value else column.is_not(None)
            case "contains":
                return column.contains(value)
            case "startswith":
                return column.startswith(value)
            case "endswith":
                return column.endswith(value)
            case "between":
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    return column.between(value[0], value[1])
                raise ValidationError(
                    f"Invalid 'between' operator: expected a list/tuple of 2 values, got {value!r}",
                    field=str(column),
                )
            case _:
                raise ValidationError(
                    f"Unsupported filter operator: {op_str}",
                )

        return None

    def _apply_ordering(
        self,
        stmt: Select,
        model_class: type,
        order_by: list,
    ) -> Select:
        """Apply ORDER BY clauses to a statement."""
        for order in order_by:
            column = getattr(model_class, order.field, None)
            if column is None:
                continue

            if order.direction == OrderDirection.DESC:
                stmt = stmt.order_by(column.desc())
            else:
                stmt = stmt.order_by(column.asc())

        return stmt

    def _apply_includes(
        self,
        stmt: Select,
        model_class: type,
        includes: list[IncludeClause],
    ) -> Select:
        """Apply eager loading for includes."""
        for include in includes:
            rel = getattr(model_class, include.relation, None)
            if rel is None:
                continue

            # Use selectinload for collections, joinedload for scalars
            # This is a simplified approach - could be optimized based on relation type
            stmt = stmt.options(selectinload(rel))

        return stmt

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
                    return func.count(column)
                return func.count()
            case "sum":
                column = getattr(model_class, field)
                return func.sum(column)
            case "avg":
                column = getattr(model_class, field)
                return func.avg(column)
            case "min":
                column = getattr(model_class, field)
                return func.min(column)
            case "max":
                column = getattr(model_class, field)
                return func.max(column)
            case _:
                raise ValueError(f"Unsupported aggregation: {operation}")

    def _get_primary_key_column(self, model_class: type) -> str:
        """Get the primary key column name for a model."""
        from sqlalchemy import inspect
        mapper = inspect(model_class)
        pk_cols = [c.key for c in mapper.primary_key]
        if pk_cols:
            return pk_cols[0]
        return DEFAULT_PRIMARY_KEY

    def _decode_cursor(self, cursor: str) -> int:
        """Decode a pagination cursor to an offset."""
        # Simple implementation: cursor is just the offset encoded as string
        try:
            return int(cursor)
        except ValueError:
            raise ValidationError(
                f"Invalid cursor format: '{cursor}'. Expected a numeric offset string.",
            )

    @staticmethod
    def encode_cursor(offset: int) -> str:
        """Encode an offset as a pagination cursor."""
        return str(offset)
