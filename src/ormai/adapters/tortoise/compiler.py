"""
Tortoise ORM query compiler.

Compiles OrmAI DSL queries into Tortoise QuerySet operations.
"""

from __future__ import annotations

from typing import Any

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


class TortoiseCompiler:
    """
    Compiles OrmAI DSL queries into Tortoise QuerySet operations.
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
            model_map: Mapping of model names to Tortoise model classes
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
        Compile a query request into a Tortoise QuerySet.
        """
        # Validate against policy and get decisions
        decision = self.policy_engine.validate_query(request, ctx)

        # Get the model class
        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Build the queryset
        queryset = model_class.all()

        # Apply filters (user filters + injected scope filters)
        all_filters = list(decision.injected_filters)
        if request.where:
            all_filters.extend(request.where)
        queryset = self._apply_filters(queryset, all_filters)

        # Apply ordering
        if request.order_by:
            queryset = self._apply_ordering(queryset, request.order_by)

        # Apply pagination
        if request.cursor:
            offset = self._decode_cursor(request.cursor)
            queryset = queryset.offset(offset)
        queryset = queryset.limit(request.take)

        # Apply includes (prefetch related)
        if request.include:
            queryset = self._apply_includes(queryset, request.include)

        return CompiledQuery(
            query=queryset,
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
        Compile a get-by-id request into a Tortoise QuerySet.
        """
        # Validate against policy
        decision = self.policy_engine.validate_get(request, ctx)

        # Get the model class
        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Get primary key field
        pk_field = self._get_primary_key_field(model_class)

        # Build the queryset
        queryset = model_class.all()

        # Apply primary key filter
        pk_filter = FilterClause(field=pk_field, op=FilterOp.EQ, value=request.id)
        all_filters = [pk_filter] + decision.injected_filters
        queryset = self._apply_filters(queryset, all_filters)

        # Apply includes
        if request.include:
            queryset = self._apply_includes(queryset, request.include)

        return CompiledQuery(
            query=queryset,
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

        Note: Tortoise aggregations are executed differently than queries.
        We store the aggregation info in the CompiledQuery for execution.
        """
        # Validate against policy
        decision = self.policy_engine.validate_aggregate(request, ctx)

        # Get the model class
        model_class = self.model_map.get(request.model)
        if model_class is None:
            raise ValueError(f"Model not found: {request.model}")

        # Build base queryset with filters
        queryset = model_class.all()

        all_filters = list(decision.injected_filters)
        if request.where:
            all_filters.extend(request.where)

        if all_filters:
            queryset = self._apply_filters(queryset, all_filters)

        # Store aggregation metadata in the query object
        # We'll process this during execution
        return CompiledQuery(
            query={
                "queryset": queryset,
                "operation": request.operation,
                "field": request.field,
            },
            request=request,
            select_fields=[],
            injected_filters=decision.injected_filters,
            policy_decisions=decision.decisions,
            timeout_ms=decision.budget.statement_timeout_ms if decision.budget else None,
        )

    def _apply_filters(
        self,
        queryset: Any,
        filters: list[FilterClause],
    ) -> Any:
        """Apply filter clauses to a queryset."""
        for f in filters:
            filter_kwargs = self._build_filter_kwargs(f)
            if filter_kwargs:
                queryset = queryset.filter(**filter_kwargs)
        return queryset

    def _build_filter_kwargs(self, f: FilterClause) -> dict[str, Any]:
        """Build Tortoise filter kwargs from a FilterClause."""
        op_str = f.op.value if isinstance(f.op, FilterOp) else f.op

        # Map our operators to Tortoise's lookup syntax
        match op_str:
            case "eq":
                return {f.field: f.value}
            case "ne":
                return {f"{f.field}__not": f.value}
            case "lt":
                return {f"{f.field}__lt": f.value}
            case "lte":
                return {f"{f.field}__lte": f.value}
            case "gt":
                return {f"{f.field}__gt": f.value}
            case "gte":
                return {f"{f.field}__gte": f.value}
            case "in":
                return {f"{f.field}__in": f.value}
            case "not_in":
                return {f"{f.field}__not_in": f.value}
            case "is_null":
                return {f"{f.field}__isnull": f.value}
            case "contains":
                return {f"{f.field}__contains": f.value}
            case "startswith":
                return {f"{f.field}__startswith": f.value}
            case "endswith":
                return {f"{f.field}__endswith": f.value}
            case _:
                return {}

    def _apply_ordering(
        self,
        queryset: Any,
        order_by: list,
    ) -> Any:
        """Apply ORDER BY clauses to a queryset."""
        order_fields = []
        for order in order_by:
            if order.direction == OrderDirection.DESC:
                order_fields.append(f"-{order.field}")
            else:
                order_fields.append(order.field)

        if order_fields:
            queryset = queryset.order_by(*order_fields)
        return queryset

    def _apply_includes(
        self,
        queryset: Any,
        includes: list[IncludeClause],
    ) -> Any:
        """Apply prefetch_related for includes."""
        prefetch_relations = [inc.relation for inc in includes]
        if prefetch_relations:
            queryset = queryset.prefetch_related(*prefetch_relations)
        return queryset

    def _get_primary_key_field(self, model_class: type) -> str:
        """Get the primary key field name for a model."""
        meta = model_class._meta
        return meta.pk_attr or "id"

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
