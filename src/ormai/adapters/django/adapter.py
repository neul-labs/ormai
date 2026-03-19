"""
Django ORM adapter implementation.

Provides query compilation and execution for Django models.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from django.db import models, transaction
from django.db.models import Q, F, Count, Sum, Min, Max, Avg

from ormai.adapters.base import CompiledQuery, OrmAdapter
from ormai.adapters.django.introspection import DjangoIntrospector
from ormai.core.context import RunContext
from ormai.core.dsl import (
    AggregateRequest,
    AggregateResult,
    CreateRequest,
    CreateResult,
    DeleteRequest,
    DeleteResult,
    FilterClause,
    GetRequest,
    GetResult,
    QueryRequest,
    QueryResult,
    UpdateRequest,
    UpdateResult,
)
from ormai.core.errors import ModelNotAllowedError, NotFoundError
from ormai.core.types import SchemaMetadata
from ormai.policy.engine import PolicyEngine
from ormai.policy.models import Policy
from ormai.policy.scoping import ScopeInjector

T = TypeVar("T")


class DjangoAdapter(OrmAdapter):
    """
    OrmAI adapter for Django ORM.

    Supports Django models with policy-governed queries.

    Usage:
        from django.apps import apps
        from ormai.adapters.django import DjangoAdapter

        adapter = DjangoAdapter(apps.get_app_config('myapp'))
    """

    def __init__(
        self,
        app_config: Any = None,
        models: list[type[models.Model]] | None = None,
    ) -> None:
        """
        Initialize the Django adapter.

        Args:
            app_config: Django AppConfig for the app (optional)
            models: Explicit list of models to include (optional)
        """
        self.app_config = app_config
        self._models = models or []
        self._introspector = DjangoIntrospector(app_config, models)
        self._model_map: dict[str, type[models.Model]] = {}

    async def introspect(self) -> SchemaMetadata:
        """Introspect Django models."""
        schema = self._introspector.introspect()
        # Build model map for quick lookup
        self._model_map = self._introspector.get_model_map()
        return schema

    def sync_introspect(self) -> SchemaMetadata:
        """Synchronous introspection."""
        schema = self._introspector.introspect()
        self._model_map = self._introspector.get_model_map()
        return schema

    def _get_model(self, model_name: str) -> type[models.Model]:
        """Get the Django model class by name."""
        if model_name not in self._model_map:
            raise ModelNotAllowedError(
                model_name,
                allowed_models=list(self._model_map.keys()),
            )
        return self._model_map[model_name]

    def compile_query(
        self,
        request: QueryRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a query request into a Django QuerySet."""
        engine = PolicyEngine(policy, schema)
        model_policy = engine.validate_model_access(request.model)

        # Get Django model class
        model_class = self._get_model(request.model)

        # Start with base queryset
        queryset = model_class.objects.all()

        # Inject scope filters
        injector = ScopeInjector(policy)
        scope_filters = injector.get_scope_filters(request.model, ctx)

        # Build Q objects for filters
        q_objects = []
        for f in scope_filters:
            q_objects.append(self._filter_to_q(f))

        # Apply request filters
        if request.where:
            for f in request.where:
                q_objects.append(self._filter_to_q(f))

        # Apply all filters
        for q in q_objects:
            queryset = queryset.filter(q)

        # Apply field selection
        select_fields = engine.filter_select_fields(
            request.model,
            request.select,
            model_policy,
        )

        if select_fields:
            queryset = queryset.values(*select_fields)

        # Apply ordering
        if request.order_by:
            order_fields = []
            for o in request.order_by:
                field = o.field
                if o.direction == "desc":
                    field = f"-{field}"
                order_fields.append(field)
            queryset = queryset.order_by(*order_fields)

        # Apply pagination
        if request.take:
            queryset = queryset[:request.take]

        return CompiledQuery(
            query=queryset,
            request=request,
            select_fields=select_fields,
            injected_filters=scope_filters,
            policy_decisions=[f"model_allowed:{request.model}"],
        )

    def compile_get(
        self,
        request: GetRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a get-by-id request."""
        engine = PolicyEngine(policy, schema)
        model_policy = engine.validate_model_access(request.model)

        model_class = self._get_model(request.model)
        queryset = model_class.objects.all()

        # Inject scope filters
        injector = ScopeInjector(policy)
        scope_filters = injector.get_scope_filters(request.model, ctx)

        for f in scope_filters:
            queryset = queryset.filter(self._filter_to_q(f))

        # Filter by primary key
        pk_field = self._get_pk_field(model_class)
        queryset = queryset.filter(**{pk_field: request.id})

        # Apply field selection
        select_fields = engine.filter_select_fields(
            request.model,
            request.select,
            model_policy,
        )

        if select_fields:
            queryset = queryset.values(*select_fields)

        return CompiledQuery(
            query=queryset,
            request=request,
            select_fields=select_fields,
            injected_filters=scope_filters,
        )

    def compile_aggregate(
        self,
        request: AggregateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile an aggregation request."""
        engine = PolicyEngine(policy, schema)
        engine.validate_model_access(request.model)

        model_class = self._get_model(request.model)
        queryset = model_class.objects.all()

        # Inject scope filters
        injector = ScopeInjector(policy)
        scope_filters = injector.get_scope_filters(request.model, ctx)

        for f in scope_filters:
            queryset = queryset.filter(self._filter_to_q(f))

        # Apply request filters
        if request.where:
            for f in request.where:
                queryset = queryset.filter(self._filter_to_q(f))

        # Store the aggregate operation info
        return CompiledQuery(
            query=queryset,
            request=request,
            injected_filters=scope_filters,
        )

    async def execute_query(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> QueryResult:
        """Execute a compiled query."""
        queryset = compiled.query

        # Execute query and convert to list
        results = list(queryset)

        # Convert model instances to dicts if needed
        data = []
        for item in results:
            if isinstance(item, dict):
                data.append(item)
            else:
                data.append(self._model_to_dict(item, compiled.select_fields))

        return QueryResult(
            data=data,
            total=len(data),
            has_more=False,  # Would need count query for accurate pagination
        )

    async def execute_get(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> GetResult:
        """Execute a compiled get request."""
        queryset = compiled.query
        request = compiled.request

        try:
            result = queryset.first()
            if result is None:
                raise NotFoundError(request.model, request.id)

            if isinstance(result, dict):
                data = result
            else:
                data = self._model_to_dict(result, compiled.select_fields)

            return GetResult(data=data, found=True)
        except Exception as e:
            if isinstance(e, NotFoundError):
                raise
            raise NotFoundError(request.model, request.id) from e

    async def execute_aggregate(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> AggregateResult:
        """Execute a compiled aggregation."""
        queryset = compiled.query
        request = compiled.request

        # Map operation to Django aggregate function
        agg_funcs = {
            "count": Count,
            "sum": Sum,
            "avg": Avg,
            "min": Min,
            "max": Max,
        }

        if request.operation not in agg_funcs:
            raise ValueError(f"Unknown aggregate operation: {request.operation}")

        agg_func = agg_funcs[request.operation]

        if request.operation == "count":
            result = queryset.aggregate(result=Count("*"))
        else:
            if not request.field:
                raise ValueError(f"Field required for {request.operation}")
            result = queryset.aggregate(result=agg_func(request.field))

        return AggregateResult(
            value=result["result"],
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
        with transaction.atomic():
            return fn(*args, **kwargs)

    def compile_create(
        self,
        request: CreateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a create request."""
        engine = PolicyEngine(policy, schema)
        engine.validate_model_access(request.model)
        engine.validate_write_access(request.model, "create")

        model_class = self._get_model(request.model)

        # Add tenant scope to data if configured
        injector = ScopeInjector(policy)
        data = dict(request.data)
        for f in injector.get_scope_filters(request.model, ctx):
            data[f.field] = f.value

        return CompiledQuery(
            query=(model_class, data),
            request=request,
            policy_decisions=["create_allowed"],
        )

    async def execute_create(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> CreateResult:
        """Execute a compiled create request."""
        model_class, data = compiled.query

        instance = model_class.objects.create(**data)

        return CreateResult(
            data=self._model_to_dict(instance),
            id=str(instance.pk),
            success=True,
        )

    def compile_update(
        self,
        request: UpdateRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile an update request."""
        engine = PolicyEngine(policy, schema)
        engine.validate_model_access(request.model)
        engine.validate_write_access(request.model, "update")

        model_class = self._get_model(request.model)
        queryset = model_class.objects.all()

        # Apply scope filters
        injector = ScopeInjector(policy)
        for f in injector.get_scope_filters(request.model, ctx):
            queryset = queryset.filter(self._filter_to_q(f))

        # Filter by ID
        pk_field = self._get_pk_field(model_class)
        queryset = queryset.filter(**{pk_field: request.id})

        return CompiledQuery(
            query=(queryset, request.data),
            request=request,
            policy_decisions=["update_allowed"],
        )

    async def execute_update(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> UpdateResult:
        """Execute a compiled update request."""
        queryset, data = compiled.query
        request = compiled.request

        updated = queryset.update(**data)

        if updated == 0:
            raise NotFoundError(request.model, request.id)

        # Fetch the updated instance
        instance = queryset.first()

        return UpdateResult(
            data=self._model_to_dict(instance) if instance else {},
            updated_count=updated,
            success=True,
        )

    def compile_delete(
        self,
        request: DeleteRequest,
        ctx: RunContext,
        policy: Policy,
        schema: SchemaMetadata,
    ) -> CompiledQuery:
        """Compile a delete request."""
        engine = PolicyEngine(policy, schema)
        engine.validate_model_access(request.model)
        engine.validate_write_access(request.model, "delete")

        model_class = self._get_model(request.model)
        queryset = model_class.objects.all()

        # Apply scope filters
        injector = ScopeInjector(policy)
        for f in injector.get_scope_filters(request.model, ctx):
            queryset = queryset.filter(self._filter_to_q(f))

        # Filter by ID
        pk_field = self._get_pk_field(model_class)
        queryset = queryset.filter(**{pk_field: request.id})

        return CompiledQuery(
            query=queryset,
            request=request,
            policy_decisions=["delete_allowed"],
        )

    async def execute_delete(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> DeleteResult:
        """Execute a compiled delete request."""
        queryset = compiled.query
        request = compiled.request

        deleted, _ = queryset.delete()

        if deleted == 0:
            raise NotFoundError(request.model, request.id)

        return DeleteResult(
            deleted_count=deleted,
            success=True,
        )

    def _filter_to_q(self, f: FilterClause) -> Q:
        """Convert a FilterClause to a Django Q object."""
        field = f.field
        value = f.value
        op = f.op

        # Map operators to Django lookups
        lookup_map = {
            "eq": "",
            "ne": "",
            "lt": "__lt",
            "le": "__lte",
            "gt": "__gt",
            "ge": "__gte",
            "in": "__in",
            "nin": "__in",
            "contains": "__icontains",
            "startswith": "__istartswith",
            "endswith": "__iendswith",
            "isnull": "__isnull",
        }

        lookup = lookup_map.get(op, "")
        key = f"{field}{lookup}"

        if op == "ne":
            return ~Q(**{field: value})
        elif op == "nin":
            return ~Q(**{key: value})
        elif op == "isnull":
            return Q(**{key: value})
        else:
            return Q(**{key: value})

    def _get_pk_field(self, model_class: type[models.Model]) -> str:
        """Get the primary key field name for a model."""
        return model_class._meta.pk.name

    def _model_to_dict(
        self,
        instance: models.Model,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Convert a model instance to a dictionary."""
        data = {}
        field_names = fields if fields else [f.name for f in instance._meta.fields]

        for name in field_names:
            if hasattr(instance, name):
                value = getattr(instance, name)
                # Handle special types
                if hasattr(value, "pk"):  # Foreign key
                    value = value.pk
                data[name] = value

        return data
